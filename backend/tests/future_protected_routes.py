# Future QR-Pay System Protected Routes

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

payment_bp = Blueprint('payments', __name__)

@payment_bp.route('/api/payments/generate-qr', methods=['POST'])
@jwt_required()  # ← Token required!
def generate_qr_code():
    """Only vendors can generate QR codes for payments"""
    claims = get_jwt()
    
    # Check if user is a vendor
    if claims.get('user_type') != 'vendor':
        return jsonify({
            'error': 'Access denied', 
            'message': 'Only vendors can generate QR codes'
        }), 403
    
    vendor_id = get_jwt_identity()
    business_shortcode = claims.get('business_shortcode')
    
    # Generate QR code logic here...
    return jsonify({
        'qr_code': 'base64_qr_image_data',
        'payment_reference': 'PAY123456',
        'vendor_shortcode': business_shortcode
    })

@payment_bp.route('/api/payments/scan-and-pay', methods=['POST'])
@jwt_required()  # ← Token required!
def scan_and_pay():
    """Only regular users can scan and pay"""
    claims = get_jwt()
    
    # Check if user is a regular user (not vendor)
    if claims.get('user_type') != 'user':
        return jsonify({
            'error': 'Access denied',
            'message': 'Only users can make payments'
        }), 403
    
    user_id = get_jwt_identity()
    user_phone = claims.get('phone')
    
    # Process payment logic here...
    return jsonify({
        'message': 'Payment initiated',
        'transaction_id': 'TXN789123',
        'amount': request.json.get('amount')
    })

@payment_bp.route('/api/payments/history', methods=['GET'])
@jwt_required()  # ← Token required!
def payment_history():
    """Both users and vendors can view their payment history"""
    claims = get_jwt()
    user_id = get_jwt_identity()
    user_type = claims.get('user_type')
    
    if user_type == 'user':
        # Show user's payment history
        return jsonify({
            'payments': ['user payment 1', 'user payment 2'],
            'user_type': 'user'
        })
    elif user_type == 'vendor':
        # Show vendor's received payments
        return jsonify({
            'received_payments': ['vendor payment 1', 'vendor payment 2'],
            'user_type': 'vendor'
        })
    else:
        return jsonify({'error': 'Invalid user type'}), 400

# ===== HOW FRONTEND USES TOKENS =====
"""
// Frontend JavaScript/React Native example

// After registration or login:
const token = response.data.access_token;
localStorage.setItem('auth_token', token);

// For subsequent API calls:
const makeAPICall = async () => {
    const token = localStorage.getItem('auth_token');
    
    const response = await fetch('/api/payments/generate-qr', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`,  // ← Token sent here!
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            amount: 1000,
            description: 'Payment for goods'
        })
    });
    
    if (response.status === 401) {
        // Token expired - redirect to login
        window.location.href = '/login';
    }
    
    return response.json();
};
"""