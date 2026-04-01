# Example: How tokens are used throughout the QR-Pay-System

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

example_bp = Blueprint('example', __name__)

# ===== REGISTRATION SCENARIO =====
"""
POST /api/auth/register/user
Body: {"name": "John", "email": "john@example.com", "password": "password123", "phone_number": "1234567890"}

Response:
{
    "message": "User registered successfully",
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",  # ← This token allows immediate app usage
    "user": {"id": 1, "name": "John", "email": "john@example.com", "phone": "1234567890"}
}

Frontend receives this and:
1. Stores the token (localStorage/sessionStorage)
2. Redirects user to dashboard (no need to login again!)
3. Uses token for subsequent API calls
"""

# ===== PROTECTED ROUTE EXAMPLES =====
@example_bp.route('/api/user/profile', methods=['GET'])
@jwt_required()  # ← This decorator requires a valid token
def get_user_profile():
    """User can access this immediately after registration because they have a token"""
    current_user_id = get_jwt_identity()  # Gets user ID from token
    claims = get_jwt()  # Gets additional claims (user_type, email, etc.)
    
    # Use the token info to fetch user data
    return jsonify({
        "user_id": current_user_id,
        "user_type": claims.get('user_type'),
        "email": claims.get('email')
    })

@example_bp.route('/api/transactions/create', methods=['POST'])
@jwt_required()
def create_transaction():
    """Both users and vendors can create transactions, but logic differs"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    user_type = claims.get('user_type')
    
    if user_type == 'user':
        # User creating a payment
        return jsonify({"message": "Payment initiated"})
    elif user_type == 'vendor':
        # Vendor creating a payment request
        return jsonify({"message": "Payment request created"})
    else:
        return jsonify({"error": "Invalid user type"}), 403

@example_bp.route('/api/vendor/dashboard', methods=['GET'])
@jwt_required()
def vendor_dashboard():
    """Only vendors should access this"""
    claims = get_jwt()
    
    if claims.get('user_type') != 'vendor':
        return jsonify({"error": "Access denied. Vendors only."}), 403
    
    # Vendor-specific dashboard data
    return jsonify({
        "business_shortcode": claims.get('business_shortcode'),
        "merchant_id": claims.get('merchant_id')
    })

# ===== TOKEN EXPIRATION & REFRESH SCENARIO =====
"""
Day 1: User registers → Gets token → Uses app (token valid)
Day 2: User opens app → Token still valid → Continues using app
Day 8: User opens app → Token expired → Frontend redirects to login
User logs in → Gets NEW token → Can use app again

This is why we need BOTH registration tokens AND login tokens!
"""