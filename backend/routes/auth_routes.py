from flask import Blueprint, request, jsonify,g
from models import User, Vendor
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt, get_jti
from extensions import db
from datetime import datetime, timezone

auth_bp = Blueprint('auth',__name__, url_prefix='/api/auth')

VALID_SHORTCODE_TYPES = {'TILL', 'PAYBILL'}


def _normalize_shortcode_type(raw_value):
    value = (raw_value or 'TILL').strip().upper()
    if value not in VALID_SHORTCODE_TYPES:
        raise ValueError('shortcode_type must be either TILL or PAYBILL')
    return value

@auth_bp.route('/register/user', methods=['POST'])
def register_user():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid or missing JSON payload'}), 400

    required_fields = ['name', 'phone_number','email','password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
        
        if not data[field]:
            return jsonify({'error': f'Field {field} cannot be empty'}), 400

    if not isinstance(data['name'], str) or not isinstance(data['phone_number'], str) or not isinstance(data['email'], str) or not isinstance(data['password'], str):
        return jsonify({'error': 'Invalid field types in request payload'}), 400

    data['name'] = data['name'].strip()
    data['phone_number'] = data['phone_number'].strip()
    data['email'] = data['email'].strip().lower()

    if not data['email'].strip() or '@' not in data['email']:
        return jsonify({'error': 'Invalid email format'}), 400

    if len(data['phone_number']) < 10:
        return jsonify({'error':'Invalid phone number'}),400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({
            'error': 'Conflict',
            'message': 'User with same email already exist'
        }), 409
    
    if User.query.filter_by(phone_number = data['phone_number']).first():
        return jsonify({
            'error': 'Conflict',
            'message':'User with the same phone number already exists'
        }), 409

    try:
        new_user = User(
            name=data['name'],
            phone_number=data['phone_number'],
            email=data['email']
        )
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        new_user.set_password(data['password'])

        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(
            identity = str(new_user.id),
            additional_claims = {
                'user_type': 'user',
                'phone_number': new_user.phone_number,
                'email': new_user.email
            }
        )

        return jsonify({
            'message': 'User registered successfully',
            'access_token': access_token,
            'user': {
                'id': new_user.id,
                'name': new_user.name,
                'phone': new_user.phone_number,
                'email': new_user.email
            }
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed', 'details': str(e)}), 500


@auth_bp.route('/register/vendor', methods=['POST'])
def register_vendor():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['name','business_shortcode','merchant_id',
                          'mcc','store_label','email','phone','password',
                          ]
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
            if not data[field]:  # Check for empty values
                return jsonify({'error': f'Field {field} cannot be empty'}), 400
        
        # Validate email format
        if not data['email'].strip() or '@' not in data['email']:
            return jsonify({'error': 'Invalid email format'}), 400
            
        # Validate phone number
        if len(data['phone']) < 10:
            return jsonify({'error': 'Invalid phone number'}), 400
        
        # Validate password length
        if len(data['password']) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Optional field validation (only if provided)
        if 'mcc' in data and data['mcc']:
            if len(data['mcc']) != 4 and len(data['mcc']) != 8:
                return jsonify({'error': 'MCC must be 4 or 8 characters'}), 400

        try:
            shortcode_type = _normalize_shortcode_type(data.get('shortcode_type'))
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400

        paybill_account_number = data.get('paybill_account_number')
        if paybill_account_number is not None:
            paybill_account_number = str(paybill_account_number).strip()
            if not paybill_account_number:
                paybill_account_number = None

        if shortcode_type == 'TILL':
            paybill_account_number = None
            
        # Check for existing vendor
        if Vendor.query.filter_by(email=data['email']).first():
            return jsonify({
                'error': 'Conflict',
                'message': 'Vendor with this email already exists'
            }), 409
            
        if Vendor.query.filter_by(business_shortcode=data['business_shortcode']).first():
            return jsonify({
                'error': 'Conflict',
                'message': 'Vendor with this business shortcode already exists'
            }), 409
            
        if Vendor.query.filter_by(phone=data['phone']).first():
            return jsonify({
                'error': 'Conflict',
                'message': 'Vendor with this phone number already exists'
            }), 409
    
        # Create new vendor with only required/provided fields
        new_vendor = Vendor(
            name=data['name'].strip(),
            business_shortcode=data['business_shortcode'].strip(),
            shortcode_type=shortcode_type,
            paybill_account_number=paybill_account_number,
            merchant_id=data['merchant_id'].strip(),
            mcc=data['mcc'].strip(),
            store_label=data['store_label'].strip(),
            email=data['email'].lower().strip(),
            phone=data['phone'].strip()
        )
        
        # Set password
        new_vendor.set_password(data['password'])

        # Save to database
        db.session.add(new_vendor)
        db.session.commit()

        # Generate JWT token
        access_token = create_access_token(
            identity=str(new_vendor.id),
            additional_claims={
                'user_type': 'vendor',
                'business_shortcode': new_vendor.business_shortcode,
                'shortcode_type': new_vendor.shortcode_type,
                'merchant_id': new_vendor.merchant_id,
                'phone': new_vendor.phone,
                'email': new_vendor.email
            }

        )
        
        return jsonify({
            'message': 'Vendor registered successfully',
            'access_token': access_token,
            'vendor': {
                'id': new_vendor.id,
                'name': new_vendor.name,
                'business_shortcode': new_vendor.business_shortcode,
                'shortcode_type': new_vendor.shortcode_type,
                'paybill_account_number': new_vendor.paybill_account_number,
                'merchant_id':new_vendor.merchant_id,
                'mcc': new_vendor.mcc,
                'store_label': new_vendor.store_label,
                'email': new_vendor.email,
                'phone':new_vendor.phone
                
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed', 'details': str(e)}), 500
            

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['email', 'password']
        
        # Validate required fields
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'Missing required field: {field}'
                }), 400
            if not data[field]:
                return jsonify({
                    'error': f'Field {field} cannot be empty'
                }), 400
        
        email = data.get('email').lower().strip()
        password = data.get('password')
        
        # Basic email validation
        if '@' not in email:
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Check if it's a user login
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            access_token = create_access_token(
                identity=str(user.id),
                additional_claims={
                    'user_type': 'user',
                    'phone': user.phone_number,
                    'email': user.email
                }
            )
            
            return jsonify({
                'message': 'Login successful',
                'access_token': access_token,
                'user_type': 'user',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'phone': user.phone_number
                }
            }), 200
        
        # Check if it's a vendor login
        vendor = Vendor.query.filter_by(email=email).first()
        if vendor and vendor.check_password(password):
            vendor.last_login = datetime.now(timezone.utc)
            db.session.commit()

            access_token = create_access_token(
                identity=str(vendor.id),
                additional_claims={
                    'user_type': 'vendor',
                    'business_shortcode': vendor.business_shortcode,
                    'shortcode_type': vendor.shortcode_type,
                    'merchant_id': vendor.merchant_id,
                    'phone': vendor.phone,
                    'email': vendor.email
                }
            )
            
            return jsonify({
                'message': 'Login successful',
                'access_token': access_token,
                'user_type': 'vendor',
                'vendor': {
                    'id': vendor.id,
                    'name': vendor.name,
                    'business_shortcode': vendor.business_shortcode,
                    'shortcode_type': vendor.shortcode_type,
                    'paybill_account_number': vendor.paybill_account_number,
                    'merchant_id': vendor.merchant_id,
                    'mcc': vendor.mcc,
                    'store_label': vendor.store_label,
                    'email': vendor.email,
                    'phone': vendor.phone,
                    'psp_id': vendor.psp_id,
                    'psp_name': vendor.psp_name
                }
            }), 200
        
        # If neither user nor vendor found, or password incorrect
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Invalid email or password'
        }), 401
        
    except Exception as e:
        return jsonify({
            'error': 'Login failed',
            'details': str(e)
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout endpoint for both users and vendors
    Uses client-side token deletion with optional server-side logging
    """
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        user_type = claims.get('user_type')
        user_email = claims.get('email')
        
        # Optional: Log logout event for security monitoring
        print(f"Logout: {user_type} ID {current_user_id} ({user_email}) at {datetime.now(timezone.utc)}")
        
        # You could also update last_logout timestamp in user/vendor table
        if user_type == 'user':
            user = User.query.get(current_user_id)
            if user:
                user.last_logout = datetime.now(timezone.utc)
                db.session.commit()
        elif user_type == 'vendor':
            vendor = Vendor.query.get(current_user_id)
            if vendor:
                vendor.last_logout = datetime.now(timezone.utc)
                db.session.commit()
        
        return jsonify({
            'message': 'Logged out successfully',
            'user_type': user_type,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Logout failed',
            'details': str(e)
        }), 500
