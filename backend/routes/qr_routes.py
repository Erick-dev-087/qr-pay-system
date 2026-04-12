from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import Vendor, QRCode, QR_Type, QRStatus, ScanLog, ScanStatus
from extensions import db
from utils.qr_utils import QR_utils
from datetime import datetime, timezone
from sqlalchemy import or_
import hashlib
import os
import secrets


qr_bp = Blueprint('qr',__name__)


def _extract_business_shortcode_from_payload(parsed_payload):
    """Resolve merchant account from provider slots in priority/fallback order."""
    psp_accounts = parsed_payload.get('psp_accounts') or {}

    # Prefer known rails first, then fallback to any populated account slot.
    preferred_slots = ['28', '29', '30', '31', '32', '33', '34', '35', '26']
    for slot in preferred_slots:
        slot_account = (psp_accounts.get(slot) or {}).get('account')
        if slot_account:
            return slot_account

    for slot_data in psp_accounts.values():
        slot_account = (slot_data or {}).get('account')
        if slot_account:
            return slot_account

    return None


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _candidate_identifiers(account_value):
    account = (account_value or '').strip()
    if not account:
        return []

    candidates = {account}

    digits = ''.join(ch for ch in account if ch.isdigit())
    if digits:
        candidates.add(digits)
        if digits.startswith('0') and len(digits) >= 10:
            candidates.add(f"254{digits[1:]}")
        if digits.startswith('254') and len(digits) >= 12:
            candidates.add(f"0{digits[3:]}")

    return list(candidates)


def _find_vendor_by_account_identifier(account_value):
    candidates = _candidate_identifiers(account_value)
    if not candidates:
        return None

    return Vendor.query.filter(
        or_(
            Vendor.business_shortcode.in_(candidates),
            Vendor.paybill_account_number.in_(candidates),
            Vendor.airtel_number.in_(candidates),
            Vendor.kcb_account.in_(candidates),
            Vendor.equity_account.in_(candidates),
            Vendor.coop_account.in_(candidates),
            Vendor.absa_account.in_(candidates),
            Vendor.ncba_account.in_(candidates),
        )
    ).first()


def _guess_shortcode_type(parsed_payload):
    additional_data_fields = parsed_payload.get('additional_data_fields') or {}
    if additional_data_fields.get('01'):
        return 'PAYBILL'
    return 'TILL'


def _normalize_mobile_candidate(raw_value):
    digits = ''.join(ch for ch in str(raw_value or '') if ch.isdigit())
    if len(digits) == 10 and digits.startswith('0'):
        return f"254{digits[1:]}"
    if len(digits) == 12 and digits.startswith('254'):
        return digits
    return None


def _build_external_candidate_response(parsed_payload, merchant_account):
    return {
        'merchant_account': merchant_account,
        'merchant_name': parsed_payload.get('merchant_name'),
        'shortcode_type': _guess_shortcode_type(parsed_payload),
        'amount': parsed_payload.get('amount'),
        'currency': parsed_payload.get('currency', '404'),
        'reference': parsed_payload.get('reference') or parsed_payload.get('additional_data'),
        'additional_data': parsed_payload.get('additional_data_fields') or {},
    }


def _create_external_vendor_and_qr(payload, parsed_payload, merchant_account):
    vendor = _find_vendor_by_account_identifier(merchant_account)

    if not vendor:
        merchant_name = (parsed_payload.get('merchant_name') or f'External Merchant {merchant_account[-4:]}')[:100]
        shortcode_type = (_guess_shortcode_type(parsed_payload) or 'TILL').strip().upper()
        currency_code = (parsed_payload.get('currency') or '404')[:3]
        merchant_city = parsed_payload.get('merchant_city') or 'External'
        mcc = (parsed_payload.get('mcc') or '0000')[:8]
        mobile_candidate = _normalize_mobile_candidate(merchant_account)

        digest = hashlib.sha256(merchant_account.encode('utf-8')).hexdigest()
        email = f"ext-{digest[:12]}@external.local"
        if mobile_candidate:
            phone = mobile_candidate
            outreach_allowed = True
        else:
            phone_seed = ''.join(ch for ch in merchant_account if ch.isdigit())
            if len(phone_seed) < 9:
                phone_seed = str(int(digest[:12], 16))
            phone = f"254{phone_seed[-9:]}"
            outreach_allowed = False

        email_counter = 1
        while Vendor.query.filter_by(email=email).first():
            email = f"ext-{digest[:12]}-{email_counter}@external.local"
            email_counter += 1

        phone_counter = 1
        while Vendor.query.filter_by(phone=phone).first():
            phone = f"254{str(int(digest[:12], 16) + phone_counter)[-9:]}"
            phone_counter += 1

        vendor = Vendor(
            name=merchant_name,
            business_shortcode=merchant_account,
            shortcode_type='PAYBILL' if shortcode_type == 'PAYBILL' else 'TILL',
            paybill_account_number=(parsed_payload.get('additional_data_fields') or {}).get('01'),
            merchant_id=f'EXT-{digest[:10]}',
            mcc=mcc,
            country_code='KE',
            currency_code=currency_code,
            store_label=merchant_city,
            email=email,
            phone=phone,
            psp_id=f'EXT-{digest[:16]}',
            psp_name='external_discovered',
            is_active=True,
        )
        vendor.set_password(secrets.token_urlsafe(32))
        db.session.add(vendor)
        db.session.flush()
    else:
        outreach_allowed = bool(vendor.psp_name == 'external_discovered' and _normalize_mobile_candidate(vendor.phone))

    qr_record = QRCode.query.filter_by(payload_data=payload).first()
    if not qr_record:
        qr_record = QRCode(
            vendor_id=vendor.id,
            payload_data=payload,
            payload_json={
                'source': 'external_confirmed',
                'verified': True,
                'merchant_account': merchant_account,
                'verification': {
                    'provider': 'user_confirmation',
                    'reason': 'User confirmed payment to external merchant',
                },
                'amount': parsed_payload.get('amount'),
                'currency': parsed_payload.get('currency'),
                'additional_data_fields': parsed_payload.get('additional_data_fields') or {},
                'external_outreach_allowed': outreach_allowed,
            },
            qr_type=QR_Type.DYNAMIC if parsed_payload.get('point_of_initiation') == '12' else QR_Type.STATIC,
            status=QRStatus.ACTIVE,
            currency_code=parsed_payload.get('currency') or '404',
            reference_number=parsed_payload.get('reference'),
        )
        db.session.add(qr_record)
        db.session.flush()

    db.session.commit()

    return vendor, qr_record

@qr_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_qrCode():
    
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    
    if claims.get('user_type') != 'vendor':
        return jsonify({'error': 'Unauthorized. Only vendors can generate QR codes'}), 403

    vendor = Vendor.query.get(current_user_id)
    if not vendor:
        return jsonify({'error': 'Vendor account not found'}), 404
        
    if not vendor.is_active:
        return jsonify({'error': 'Vendor account is inactive'}), 403

    data = request.get_json() or {}
    

    qr_type_str = data.get('qr_type', 'STATIC').upper()
    qr_profile = str(data.get('qr_profile', 'UNIVERSAL')).upper()
    try:
        qr_type = QR_Type[qr_type_str]
    except KeyError:
        return jsonify({'error': 'Invalid QR type. Must be STATIC or DYNAMIC'}), 400

    if qr_profile not in {'UNIVERSAL', 'LEGACY_ADAPTIVE'}:
        return jsonify({'error': 'Invalid qr_profile. Must be UNIVERSAL or LEGACY_ADAPTIVE'}), 400

    
    if qr_type == QR_Type.STATIC:
        existing_qr = QRCode.query.filter_by(
            vendor_id=vendor.id, 
            qr_type=QR_Type.STATIC, 
            status=QRStatus.ACTIVE
        ).first()
        
        if existing_qr:
            return jsonify({
                'message': 'Active static QR code already exists',
                'qr_code': {
                    'id': existing_qr.id,
                    'payload': existing_qr.payload_data,
                    'type': existing_qr.qr_type.value
                }
            }), 200

    
    try:
        qr_generator = QR_utils(vendor)
        use_universal = qr_profile == 'UNIVERSAL'
        reference = data.get('reference')
        
        if qr_type == QR_Type.STATIC:
            if use_universal:
                _, _, qr_record = qr_generator.generate_production_qr(
                    amount=None,
                    reference=reference,
                    save_to_db=True,
                )
            else:
                _, _, qr_record = qr_generator.generate_till_qr(save_to_db=True)
        else:
            
            amount = data.get('amount')
            if amount is None:
                return jsonify({'error': 'Amount is required for Dynamic QR'}), 400

            if use_universal:
                _, _, qr_record = qr_generator.generate_production_qr(
                    amount=amount,
                    reference=reference,
                    save_to_db=True,
                )
            else:
                _, _, qr_record = qr_generator.generate_transaction_qr(
                    trx_type="BG",
                    amount=amount,
                    reference=reference,
                    save_to_db=True,
                )
            

        return jsonify({
            'message': 'QR code generated successfully',
            'qr_code': {
                'id': qr_record.id,
                'payload': qr_record.payload_data,
                'type': qr_record.qr_type.value,
                'profile': qr_profile.lower(),
            }
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to generate QR code', 'details': str(e)}), 500


@qr_bp.route('/scan', methods=['POST'])
@jwt_required()
def scan_qr():
    """Scan and validate a QR code, log the scan, and return vendor info"""
    try:
       
        current_user_id = get_jwt_identity()
        try:
            current_user_id_int = int(current_user_id)
        except (TypeError, ValueError):
            current_user_id_int = current_user_id
        claims = get_jwt()
        user_type = claims.get('user_type')
        
        data = request.get_json()
        if not data or 'payload' not in data:
            return jsonify({'error': 'Payload is required'}), 400
        
        payload = data.get('payload', '').strip()
        if not payload:
            return jsonify({'error': 'Payload cannot be empty'}), 400

        confirm_external_payment = _as_bool(data.get('confirm_external_payment', False), default=False)
        

        if not QR_utils.validate_crc(payload):
            return jsonify({'error': 'Invalid QR code: checksum validation failed'}), 400
        
        # 4. Parse the payload to extract fields
        try:
            parsed = QR_utils.parse_payload(payload)
        except ValueError as e:
            return jsonify({'error': f'Invalid QR format: {str(e)}'}), 400
        
        # 5. Validate required fields
        business_shortcode = _extract_business_shortcode_from_payload(parsed)
        if not business_shortcode:
            return jsonify({'error': 'Invalid QR: missing business shortcode'}), 400
        
        # 6. Find the vendor by account/shortcode across supported account rails
        vendor = _find_vendor_by_account_identifier(business_shortcode)
        qr_record = QRCode.query.filter_by(payload_data=payload).first()
        allow_external_qr = _env_bool('ALLOW_EXTERNAL_QR', False)
        require_confirmation = _env_bool('EXTERNAL_QR_REQUIRE_USER_CONFIRMATION', True)
        auto_onboard = _env_bool('AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM', True)

        if not vendor:
            if not allow_external_qr:
                return jsonify({'error': 'Vendor not found for this QR code'}), 404

            if require_confirmation and not confirm_external_payment:
                return jsonify({
                    'message': 'This merchant is not registered with our platform. Do you want to continue anyway?',
                    'valid': True,
                    'requires_confirmation': True,
                    'can_initiate_payment': False,
                    'external_merchant': _build_external_candidate_response(parsed, business_shortcode),
                    'next_step': 'Resend this request with confirm_external_payment=true to continue.',
                }), 200

            if auto_onboard:
                vendor, qr_record = _create_external_vendor_and_qr(payload, parsed, business_shortcode)
            else:
                return jsonify({
                    'message': 'External QR accepted by user confirmation',
                    'valid': True,
                    'requires_confirmation': False,
                    'can_initiate_payment': False,
                    'external_merchant': _build_external_candidate_response(parsed, business_shortcode),
                    'next_step': 'Enable AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM to continue to payment initiation.',
                }), 200
        
        # 7. Check if vendor is active
        if not vendor.is_active:
            return jsonify({'error': 'This vendor is not currently accepting payments'}), 403
        
        # 8. Find the QR record in database
        if not qr_record:
            return jsonify({'error': 'QR code not found in system'}), 404
        
        # 9. Check if QR is active
        if qr_record.status != QRStatus.ACTIVE:
            return jsonify({'error': f'QR code is {qr_record.status.value}'}), 400
        
        # 10. Prevent vendor from scanning their own QR (optional security check)
        if user_type == 'vendor' and vendor.id == current_user_id_int:
            return jsonify({'error': 'Vendors cannot scan their own QR codes'}), 403
        
        # 11. Create scan log
        from models import ScanLog, ScanStatus
        scan_log = ScanLog(
            qr_id=qr_record.id,
            user_id=current_user_id_int,
            status=ScanStatus.SCANNED_ONLY
        )
        db.session.add(scan_log)
        
        # 12. Update QR last scanned timestamp
        qr_record.last_scanned_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # 13. Return vendor and QR info to user
        return jsonify({
            'message': 'QR scanned successfully',
            'vendor': {
                'id': vendor.id,
                'name': vendor.name,
                'business_shortcode': vendor.business_shortcode,
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': vendor.paybill_account_number,
                'store_label': vendor.store_label
            },
            'qr_code': {
                'id': qr_record.id,
                'type': qr_record.qr_type.value,
                'amount': parsed.get('amount'),  # May be None for static QR
                'reference': parsed.get('reference') or parsed.get('additional_data'),
                'additional_data': parsed.get('additional_data_fields') or {},
                'currency': parsed.get('currency', '404'),
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': (parsed.get('additional_data_fields') or {}).get('01') or vendor.paybill_account_number
            },
            'requires_confirmation': False,
            'next_step': 'Use /api/payment/initiate to complete the payment'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Scan failed', 'details': str(e)}), 500


@qr_bp.route('/validate', methods=['POST'])
@jwt_required()
def validate_qr():
    """Validate a QR code without logging a scan (read-only check)"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')

        data = request.get_json()
        if not data or 'payload' not in data:
            return jsonify({'error': 'Payload is required'}), 400
            
        payload = data.get('payload', '').strip()
        if not payload:
            return jsonify({'error': 'Payload cannot be empty'}), 400

        confirm_external_payment = _as_bool(data.get('confirm_external_payment', False), default=False)
        
        if not QR_utils.validate_crc(payload):
            return jsonify({'error': 'Invalid QR code: checksum validation failed'}), 400
        
       
        try:
            parsed = QR_utils.parse_payload(payload)
        except ValueError as e:
            return jsonify({'error': f'Invalid QR format: {str(e)}'}), 400
            
        
        business_shortcode = _extract_business_shortcode_from_payload(parsed)
        if not business_shortcode:
            return jsonify({'error': 'Invalid QR: missing business shortcode'}), 400
            
        vendor = _find_vendor_by_account_identifier(business_shortcode)
        qr_record = QRCode.query.filter_by(payload_data=payload).first()
        allow_external_qr = _env_bool('ALLOW_EXTERNAL_QR', False)
        require_confirmation = _env_bool('EXTERNAL_QR_REQUIRE_USER_CONFIRMATION', True)
        auto_onboard = _env_bool('AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM', True)

        if not vendor:
            if not allow_external_qr:
                return jsonify({'error': 'Vendor not found for this QR Code'}), 404

            if require_confirmation and not confirm_external_payment:
                return jsonify({
                    'message': 'This merchant is not registered with our platform. Do you want to continue anyway?',
                    'valid': True,
                    'requires_confirmation': True,
                    'can_initiate_payment': False,
                    'external_merchant': _build_external_candidate_response(parsed, business_shortcode),
                    'qr_code': {
                        'id': None,
                        'amount': parsed.get('amount'),
                        'reference': parsed.get('reference') or parsed.get('additional_data'),
                        'additional_data': parsed.get('additional_data_fields') or {},
                        'currency': parsed.get('currency', '404'),
                    },
                    'next_step': 'Resend this request with confirm_external_payment=true to continue.',
                }), 200

            if auto_onboard:
                vendor, qr_record = _create_external_vendor_and_qr(payload, parsed, business_shortcode)
            else:
                return jsonify({
                    'message': 'External QR accepted by user confirmation',
                    'valid': True,
                    'requires_confirmation': False,
                    'can_initiate_payment': False,
                    'external_merchant': _build_external_candidate_response(parsed, business_shortcode),
                    'next_step': 'Enable AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM to continue to payment initiation.',
                }), 200
        
        
        if not vendor.is_active:
            return jsonify({'error': 'This vendor is currently not accepting payments'}), 403
        
        if not qr_record:
            return jsonify({'error': 'QR code not found in the system'}), 404
        
        
        if qr_record.status != QRStatus.ACTIVE:
            return jsonify({'error': f'QR code is {qr_record.status.value}'}), 400
        
        # Return validation result (no scan logging)
        return jsonify({
            'message': 'QR code is valid and ready for payment',
            'valid': True,
            'vendor': {
                'id': vendor.id,
                'name': vendor.name,
                'business_shortcode': vendor.business_shortcode,
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': vendor.paybill_account_number,
                'store_label': vendor.store_label
            },
            'qr_code': {
                'id': qr_record.id,
                'type': qr_record.qr_type.value,
                'amount': parsed.get('amount'),  # May be None for static QR
                'reference': parsed.get('reference') or parsed.get('additional_data'),
                'additional_data': parsed.get('additional_data_fields') or {},
                'currency': parsed.get('currency', '404'),
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': (parsed.get('additional_data_fields') or {}).get('01') or vendor.paybill_account_number
            },
            'requires_confirmation': False,
            'can_initiate_payment': True
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Validation failed', 'details': str(e)}), 500

        

        
    