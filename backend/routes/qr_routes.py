from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import Vendor, QRCode, User, QR_Type, QRStatus, ScanLog, ScanStatus
from extensions import db
from utils.qr_utils import QR_utils
from datetime import datetime, timezone


qr_bp = Blueprint('qr',__name__)


def _extract_business_shortcode_from_payload(parsed_payload):
    """Resolve merchant account from provider slots in priority/fallback order."""
    psp_accounts = parsed_payload.get('psp_accounts') or {}

    # Prefer known rails first, then fallback to any populated account slot.
    preferred_slots = ['28', '29', '30', '31', '32', '33', '34', '26']
    for slot in preferred_slots:
        slot_account = (psp_accounts.get(slot) or {}).get('account')
        if slot_account:
            return slot_account

    for slot_data in psp_accounts.values():
        slot_account = (slot_data or {}).get('account')
        if slot_account:
            return slot_account

    return None

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

    data = request.get_json()
    

    qr_type_str = data.get('qr_type', 'STATIC').upper()
    try:
        qr_type = QR_Type[qr_type_str]
    except KeyError:
        return jsonify({'error': 'Invalid QR type. Must be STATIC or DYNAMIC'}), 400

    
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
        
        if qr_type == QR_Type.STATIC:
            _, _, qr_record = qr_generator.generate_till_qr(save_to_db=True)
        else:
            
            amount = data.get('amount')
            if not amount:
                return jsonify({'error': 'Amount is required for Dynamic QR'}), 400
            
            _, _, qr_record = qr_generator.generate_transaction_qr(
                trx_type="BG",
                amount=amount,
                reference=None,
                save_to_db=True,
            )
            

        return jsonify({
            'message': 'QR code generated successfully',
            'qr_code': {
                'id': qr_record.id,
                'payload': qr_record.payload_data,
                'type': qr_record.qr_type.value
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
        
        # 6. Find the vendor by business shortcode
        vendor = Vendor.query.filter_by(business_shortcode=business_shortcode).first()
        if not vendor:
            return jsonify({'error': 'Vendor not found for this QR code'}), 404
        
        # 7. Check if vendor is active
        if not vendor.is_active:
            return jsonify({'error': 'This vendor is not currently accepting payments'}), 403
        
        # 8. Find the QR record in database
        qr_record = QRCode.query.filter_by(payload_data=payload).first()
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
                'reference': parsed.get('additional_data'),
                'currency': parsed.get('currency', '404'),
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': vendor.paybill_account_number
            },
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
        
        if not QR_utils.validate_crc(payload):
            return jsonify({'error': 'Invalid QR code: checksum validation failed'}), 400
        
       
        try:
            parsed = QR_utils.parse_payload(payload)
        except ValueError as e:
            return jsonify({'error': f'Invalid QR format: {str(e)}'}), 400
            
        
        business_shortcode = _extract_business_shortcode_from_payload(parsed)
        if not business_shortcode:
            return jsonify({'error': 'Invalid QR: missing business shortcode'}), 400
            
       
        vendor = Vendor.query.filter_by(business_shortcode=business_shortcode).first()
        if not vendor:
            return jsonify({'error': 'Vendor not found for this QR Code'}), 404
        
        
        if not vendor.is_active:
            return jsonify({'error': 'This vendor is currently not accepting payments'}), 403
        
       
        qr_record = QRCode.query.filter_by(payload_data=payload).first()
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
                'reference': parsed.get('additional_data'),
                'currency': parsed.get('currency', '404'),
                'shortcode_type': vendor.shortcode_type,
                'paybill_account_number': vendor.paybill_account_number
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Validation failed', 'details': str(e)}), 500

        

        
    