from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from extensions import db, limiter
from datetime import datetime, timezone
from models import PaymentSession,Transaction, User,Vendor,QRCode,QR_Type,QRStatus,TransactionStatus,PaymentStatus
from utils.daraja_service import DarajaService, TransactionType
from utils.mpese_mock import MockMpesaService
from utils.sms_service import send_sms, build_external_merchant_pitch_message
import os
from sqlalchemy.exc import IntegrityError

payment_bp = Blueprint('payment',__name__)


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _normalize_msisdn(phone_number):
    """Normalize Kenyan phone numbers into 2547XXXXXXXX format."""
    digits = ''.join(ch for ch in str(phone_number or '') if ch.isdigit())
    if len(digits) == 12 and digits.startswith('254'):
        return digits
    if len(digits) == 10 and digits.startswith('0'):
        return f"254{digits[1:]}"
    if len(digits) == 9 and digits.startswith('7'):
        return f"254{digits}"
    return None


def _resolve_transaction_type(vendor):
    """Resolve Daraja transaction type with sandbox-friendly fallback."""
    shortcode_type = (getattr(vendor, 'shortcode_type', 'TILL') or 'TILL').upper()
    base_url = str(os.getenv('DARAJA_BASE_URL', '')).strip().lower()
    is_sandbox = 'sandbox.safaricom.co.ke' in base_url
    force_bill_payment = _as_bool(os.getenv('DARAJA_FORCE_BILL_PAYMENT'), default=is_sandbox)

    if shortcode_type == 'TILL' and not force_bill_payment:
        return TransactionType.BUY_GOODS
    return TransactionType.BILL_PAYMENT

@payment_bp.route('/initiate', methods=['POST'])
@limiter.limit('10 per minute')
@jwt_required()
def initiate_payment():
    """
    Initiates a payment transaction
    - Validates payer (user or vendor, but vendor can't pay themselves)
    - Creates a transaction record
    - Triggers M-Pesa STK push
    - Returns transaction ID
    - Supports both bill payment and goods/services transaction types
    """
    try:
        
        current_user_id = get_jwt_identity()
        try:
            current_user_id = int(current_user_id)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Invalid token identity'
            }), 401
        claims = get_jwt()
        user_type = claims.get('user_type')

        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['qr_code_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        qr_code_id = data.get('qr_code_id')
        
        
        qr_code = QRCode.query.get(qr_code_id)
        if not qr_code:
            return jsonify({
                'error': 'QR code not found',
                'message': 'The provided QR code does not exist'
            }), 404
        
        if qr_code.status != QRStatus.ACTIVE:
            return jsonify({
                'error': 'Inactive QR Code',
                'message': 'This QR code is no longer active'
            }), 400
        
        
        payee_vendor = qr_code.vendor
        if not payee_vendor:
            return jsonify({'error': 'Vendor not found for this QR code'}), 404
        
        if not payee_vendor.is_active:
            return jsonify({
                'error': 'Vendor inactive',
                'message': 'This vendor is currently not accepting payments through this QR code'
            }), 400
        
        
        active_phone = None
        payer_user_id = None
        if user_type == 'vendor':
            active_payer = Vendor.query.get(current_user_id)
            if not active_payer:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Vendor account not found'
                }), 401
            
            
            if active_payer.id == payee_vendor.id:
                return jsonify({
                    'error': 'Invalid transaction',
                    'message': 'Vendors cannot pay themselves'
                }), 400
            
            active_phone = active_payer.phone
            
        elif user_type == 'user':
            active_payer = User.query.get(current_user_id)
            if not active_payer:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'User account not found'
                }), 401
            
            active_phone = active_payer.phone_number
            payer_user_id = active_payer.id
        else:
            return jsonify({
                'error': 'Invalid user type',
                'message': 'Unknown user type in token'
            }), 400
        
       
        active_phone = _normalize_msisdn(active_phone)
        if not active_phone:
            return jsonify({
                'error': 'Invalid phone number',
                'message': 'Use a valid Kenyan number in 07XXXXXXXX, 7XXXXXXXX, or 2547XXXXXXXX format'
            }), 400
        
       
        amount = None
        if qr_code.qr_type == QR_Type.DYNAMIC:
        
            amount = qr_code.payload_json.get('amount') if qr_code.payload_json else None
            if not amount:
                return jsonify({
                    'error': 'Amount not found',
                    'message': 'Dynamic QR code missing amount information'
                }), 400
        else:
            
            amount = data.get('amount')
            if not amount:
                return jsonify({
                    'error': 'Amount required',
                    'message': 'Please provide payment amount for static QR code'
                }), 400
        
       
        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify({'error': 'Amount must be greater than 0'}), 400
            if amount > 500000:
                return jsonify({'error': 'Amount exceeds maximum limit of 500,000 KES'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount format'}), 400
        
        
        initiated_at = datetime.now(timezone.utc)
        
        transaction = Transaction(
            amount=amount,
            status=TransactionStatus.PENDING,
            phone=active_phone,
            initated_at=initiated_at,
            user_id=payer_user_id,
            vendor_id=payee_vendor.id,
            qrcode_id=qr_code_id
        )
        
        db.session.add(transaction)
        db.session.flush()  
        
       
        if payer_user_id is not None:
            payment_session = PaymentSession(
                amount=amount,
                status=PaymentStatus.PAYMENT_INITIATED,
                started_at=initiated_at,
                qr_id=qr_code_id,
                user_id=payer_user_id,
                transaction_id=transaction.id,
            )
            db.session.add(payment_session)

        try:
            db.session.commit()
        except IntegrityError as err:
            db.session.rollback()
            return jsonify({
                'error': 'Payment initiation failed',
                'message': 'Unable to create payment records. Please verify account setup and try again.',
                'details': str(err.orig)
            }), 500
        
        daraja_transaction_type = _resolve_transaction_type(payee_vendor)
        
        # Use Daraja Service for real API or mock for testing
        try:
            daraja_service = DarajaService()
            mpesa_response = daraja_service.initiate_stk_push(
                phone_number=active_phone,
                amount=int(amount),
                account_reference=f'TXN-{transaction.id}',
                transaction_desc=f'Payment to {payee_vendor.name}',
                transaction_type=daraja_transaction_type
            )
        except Exception as e:
            # Fall back to mock service for development
            mpesa_service = MockMpesaService()
            mpesa_response = mpesa_service.initiate_stk_push(
                business_shortcode=payee_vendor.business_shortcode,
                amount=int(amount),
                phone_number=active_phone,
                transaction_id=transaction.id,
                account_reference=f'TXN-{transaction.id}',
                transaction_desc=f'Payment to {payee_vendor.name}',
                callback_url=request.host_url.rstrip('/') + '/api/payment/stk_callback'
            )
        
        if not mpesa_response.get('success'):
            current_msg = mpesa_response.get('message', 'Unknown error')

            # Automatic sandbox retry: BUY_GOODS often fails in Daraja sandbox.
            if daraja_transaction_type == TransactionType.BUY_GOODS:
                retry_response = DarajaService().initiate_stk_push(
                    phone_number=active_phone,
                    amount=int(amount),
                    account_reference=f'TXN-{transaction.id}',
                    transaction_desc=f'Payment to {payee_vendor.name}',
                    transaction_type=TransactionType.BILL_PAYMENT
                )
                if retry_response.get('success'):
                    mpesa_response = retry_response
                    daraja_transaction_type = TransactionType.BILL_PAYMENT
                else:
                    current_msg = retry_response.get('message', current_msg)

            if not mpesa_response.get('success'):
                return jsonify({
                    'error': 'Failed to initiate payment',
                    'message': current_msg,
                    'hint': 'Verify Daraja credentials, transaction type, callback URL, and network reachability'
                }), 502

        if not mpesa_response.get('success'):
            return jsonify({
                'error': 'Failed to initiate payment',
                'message': mpesa_response.get('message', 'Unknown error')
            }), 502
        
        
        return jsonify({
            'message': 'Payment initiated successfully',
            'transaction_id': transaction.id,
            'checkout_request_id': mpesa_response.get('checkout_request_id'),
            'amount': amount,
            'vendor': {
                'name': payee_vendor.name,
                'business_shortcode': payee_vendor.business_shortcode
            },
            'transaction_type': daraja_transaction_type.value,
            'status': 'Pending',
            'instructions': 'Please check your phone and enter your M-Pesa PIN to complete the payment'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Payment initiation failed',
            'details': str(e)
        }), 500


@payment_bp.route('/stk_callback', methods=['POST'])
@limiter.limit('120 per minute')
def daraja_callback():
    """
    Handles M-Pesa/Daraja STK Push callback
    - Receives payment confirmation from Daraja
    - Updates transaction status
    - Implements idempotency (processes callback only once)
    - Stores receipt number and callback metadata
    """
    try:
       
        data = request.get_json()
        if not data:
            return jsonify({'ResultCode': 1, 'ResultDesc': 'No data provided'}), 200
        
        
        callback = data.get('Body', {}).get('stkCallback', {})
        
        
        if not callback:
            callback = data
        
        checkout_request_id = callback.get('CheckoutRequestID') or callback.get('checkout_request_id')
        merchant_request_id = callback.get('MerchantRequestID') or callback.get('merchant_request_id')
        result_code = callback.get('ResultCode', -1)
        result_desc = callback.get('ResultDesc', 'Unknown')
        
        if not checkout_request_id:
            
            print(f"⚠️ Callback missing CheckoutRequestID: {data}")
            return jsonify({'ResultCode': 0, 'ResultDesc': 'Acknowledged'}), 200
        
        
        metadata = {}
        callback_metadata = callback.get('CallbackMetadata', {})
        if callback_metadata:
            items = callback_metadata.get('Item', [])
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                if name:
                    metadata[name] = value
        
        # Try to find transaction - for now using phone and amount as fallback
        # In production, you should store checkout_request_id on Transaction during initiation
        phone = metadata.get('PhoneNumber') or callback.get('phone_number')
        amount = metadata.get('Amount') or callback.get('amount')
        
        # Find most recent pending transaction matching phone/amount
        transaction = None
        if phone and amount:
            transaction = Transaction.query.filter_by(
                phone=str(phone),
                amount=float(amount),
                status=TransactionStatus.PENDING
            ).order_by(Transaction.initated_at.desc()).first()
        
        if not transaction:
            # Log for reconciliation but acknowledge receipt
            print(f"⚠️ Transaction not found for checkout_id: {checkout_request_id}")
            print(f"   Phone: {phone}, Amount: {amount}")
            # Store orphaned callback for manual reconciliation
            return jsonify({'ResultCode': 0, 'ResultDesc': 'Acknowledged'}), 200
        
        # 4. Idempotency check - has this callback been processed?
        if transaction.callback_response:
            print(f"ℹ️ Duplicate callback for transaction {transaction.id} - ignoring")
            return jsonify({'ResultCode': 0, 'ResultDesc': 'Already processed'}), 200
        
        # 5. Process callback based on result code
        if result_code == 0:
            # Success
            transaction.status = TransactionStatus.SUCCESS
            transaction.mpesa_receipt = metadata.get('MpesaReceiptNumber') or callback.get('receipt_number')
            transaction.completed_at = datetime.utcnow()
            
            # Update payment session if exists
            payment_session = PaymentSession.query.filter_by(
                transaction_id=transaction.id
            ).first()
            if payment_session:
                payment_session.status = PaymentStatus.PAYMENT_PENDING  # Or create SUCCESS status

            # Optional growth loop: notify externally discovered merchants.
            vendor = transaction.vendor
            qr_payload_json = (transaction.qr_code.payload_json or {}) if transaction.qr_code else {}
            should_pitch_external = (
                vendor is not None
                and vendor.psp_name == 'external_discovered'
                and bool(qr_payload_json.get('external_outreach_allowed'))
                and str(os.getenv('ENABLE_EXTERNAL_MERCHANT_SMS_PITCH', 'true')).strip().lower() in {'1', 'true', 'yes', 'on'}
            )

            if should_pitch_external:
                message = build_external_merchant_pitch_message(
                    amount=transaction.amount,
                    download_url=os.getenv('APP_DOWNLOAD_URL', '').strip(),
                )
                sent, sms_info = send_sms(vendor.phone, message)
                if sent:
                    print(f"📩 External merchant outreach SMS sent for TXN {transaction.id}")
                else:
                    print(f"⚠️ External merchant outreach SMS skipped for TXN {transaction.id}: {sms_info}")
            
            print(f"✅ Payment successful: TXN {transaction.id}, Receipt: {transaction.mpesa_receipt}")
        else:
            # Failed
            transaction.status = TransactionStatus.FAILED
            transaction.completed_at = datetime.utcnow()
            
            # Update payment session
            payment_session = PaymentSession.query.filter_by(
                transaction_id=transaction.id
            ).first()
            if payment_session:
                payment_session.status = PaymentStatus.PAYMENT_EXPIRED
            
            print(f"❌ Payment failed: TXN {transaction.id}, Reason: {result_desc}")
        
        # 6. Store full callback for audit
        transaction.callback_response = data
        
        # 7. Commit changes
        db.session.commit()
        
        # 8. Return 200 OK to Daraja (required)
        return jsonify({
            'ResultCode': 0,
            'ResultDesc': 'Callback processed successfully'
        }), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error processing callback: {str(e)}")
        # Still return 200 to avoid retries
        return jsonify({
            'ResultCode': 0,
            'ResultDesc': 'Error logged'
        }), 200

@payment_bp.route('/<int:transaction_id>/status', methods=['GET'])
@limiter.limit('60 per minute')
@jwt_required()
def get_transaction_status(transaction_id):
    """
    Check the status of a transaction
    Useful for testing and frontend polling
    """
    try:
        transaction = Transaction.query.get(transaction_id)
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Verify user owns this transaction
        current_user_id = int(get_jwt_identity())  # Convert to int for comparison
        claims = get_jwt()
        user_type = claims.get('user_type')
        
        if user_type == 'user':
            # Check if this user initiated the transaction
            if transaction.user_id != current_user_id:
                return jsonify({'error': 'Unauthorized'}), 403
        elif user_type == 'vendor':
            if transaction.vendor_id != current_user_id:
                return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'id': transaction.id,
            'status': transaction.status.value,
            'amount': transaction.amount,
            'phone': transaction.phone,
            'mpesa_receipt': transaction.mpesa_receipt,
            'initiated_at': transaction.initated_at.isoformat(),
            'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/ping', methods=['GET'])
@limiter.limit('30 per minute')
def callback_ping():
    """Simple endpoint to test if callback URL is publicly accessible"""
    return jsonify({
        'status': 'ok',
        'message': 'Callback endpoint is reachable',
        'endpoint': '/api/payment/stk_callback'
    }), 200
