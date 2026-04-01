from flask import Blueprint,jsonify, request
from models import Vendor,Transaction
from extensions import db
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from utils.vendor_analytics_utils import (
    get_vendor_dashboard_summary,
    get_vendor_cash_flow,
    get_vendor_net_flow,
    get_vendor_top_customers,
    get_vendor_largest_transactions,
    get_vendor_outflow_breakdown,
    get_vendor_spending_ratio,
    get_vendor_weekly_performance
)

vendor_bp = Blueprint('vendor',__name__)

@vendor_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current vendor's profile information"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()

    if claims.get('user_type') != 'vendor':
        return jsonify({
            'error': 'Unauthorized. Only registered vendors can access this endpoint'
        }), 403
    
    vendor = Vendor.query.get(current_user_id)
    if not vendor:
        return jsonify({'error': 'Vendor not found'}), 404
    
    return jsonify({
        "message": "Vendor profile retrieved successfully",
        "vendor": {
            "id": vendor.id,
            "name": vendor.name,
            "business_shortcode": vendor.business_shortcode,
            "merchant_id": vendor.merchant_id,
            "mcc": vendor.mcc,
            "store_label": vendor.store_label,
            "email": vendor.email,
            "phone": vendor.phone,
            "is_active": vendor.is_active,
            "created_at": vendor.created_at.isoformat() if vendor.created_at else None,
            "updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None
        }
    }), 200


@vendor_bp.route('/profile',methods=['PUT'])
@jwt_required()
def update_profile():
    """Update current vendor's profile information"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != "vendor":
            return jsonify({'error': 'Unauthorized. Only registerd vendors can access this endpoint'}), 403
        
        vendor = Vendor.query.get(current_user_id)
        if not vendor:
            return jsonify({'error':'Vendor not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({'error': 'Name cannot be empty'}),400
            vendor.name = name
        
        if "business_shortcode" in data:
            bs = data['business_shortcode'].strip()
            if not bs:
                return jsonify({'error': 'Business shortcode cannot be empty'}),400
            
            existing = Vendor.query.filter(Vendor.business_shortcode == bs , Vendor.id != current_user_id).first()
            if existing:
                return jsonify({'error': 'Business shortcode is already in use'}),409
            
            vendor.business_shortcode = bs

        if "email" in data:
            email = data['email'].strip()
            if not email:
                return jsonify({'error': 'Email cannot be empty'}),400

            existing = Vendor.query.filter(Vendor.email == email, Vendor.id != current_user_id).first()
            if existing:
                return jsonify({'error':'Email already in use'}), 409
            vendor.email = email

        if "phone" in data:
            phone = data['phone'].strip()
            if not phone:
                return jsonify({'error': "Phone cannot be empty"}),409
            vendor.phone= phone

        db.session.commit()

        return jsonify({
            "message": "Vendor profile updated successfully",
            "vendor":{
                "id": vendor.id,
                "name": vendor.name,
                "business_shortcode": vendor.business_shortcode,
                "merchant_id": vendor.merchant_id,
                "mcc": vendor.mcc,
                "store_label": vendor.store_label,
                "email": vendor.email,
                "phone": vendor.phone,
                "is_active": vendor.is_active,
                "created_at": vendor.created_at.isoformat() if vendor.created_at else None,
                "updated_at": vendor.updated_at.isoformat() if vendor.updated_at else None
            }
        }), 200
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'error': 'Email , phone or business shortcode was already in use'
        }), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to update user profile',
            'details': str(e)
        }), 500
    

@vendor_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get all transactions for the current vendor"""

    current_user_id = get_jwt_identity()
    claims = get_jwt()

    if claims.get('user_type') != 'vendor':
        return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Limit per_page to prevent abuse
    per_page = min(per_page, 100)
    
    # Query with pagination
    pagination = Transaction.query.filter_by(vendor_id=current_user_id)\
        .order_by(Transaction.initated_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    transactions = pagination.items

    return jsonify({
        "message": "Transaction history retrieved successfully",
        "transactions": [
            {
                "id": transaction.id,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "status": transaction.status.value,  # Enum to string
                "mpesa_receipt": transaction.mpesa_receipt,
                "phone": transaction.phone,
                "initiated_at": transaction.initated_at.isoformat() if transaction.initated_at else None,
                "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
                "vendor_id": transaction.vendor_id,
                "qrcode_id": transaction.qrcode_id
            } for transaction in transactions
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }
    }), 200


@vendor_bp.route('/transactions/<int:transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """Get specific transaction details for the current vendor"""
    
    current_user_id = get_jwt_identity()
    claims = get_jwt()

    if claims.get('user_type') != 'vendor':
        return jsonify({'error': 'Unauthorized. Only registered vendors can access this endpoint'}), 403
    
    # SECURITY: Filter by BOTH transaction_id AND vendor_id to prevent accessing other vendors' transactions
    transaction = Transaction.query.filter_by(id=transaction_id, vendor_id=current_user_id).first()
    if not transaction:
        return jsonify({'error': 'Transaction not found or access denied'}), 404
    
    return jsonify({
        "message": "Transaction retrieved successfully",
        "transaction": {
            "id": transaction.id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status.value,
            "mpesa_receipt": transaction.mpesa_receipt,
            "phone": transaction.phone,
            "callback_response": transaction.callback_response,
            "initiated_at": transaction.initated_at.isoformat() if transaction.initated_at else None,
            "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
            "user_id": transaction.user_id,
            "qrcode_id": transaction.qrcode_id
        }
    }), 200


@vendor_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    """
    Get comprehensive analytics dashboard for the vendor.
    Includes cash flow, net flow, top customers, largest transactions, 
    outflow breakdown, spending ratios, and weekly performance.
    
    Query Parameters:
    - days: Number of days for analysis (default: 30, max: 365)
    - weeks: Number of weeks for weekly performance (default: 4, max: 52)
    """
    try:
        # 1. AUTHENTICATION: Verify vendor identity
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != 'vendor':
            return jsonify({'error': 'Unauthorized. Only registered vendors can access this endpoint'}), 403
        
        # 2. VERIFY VENDOR EXISTS
        vendor = Vendor.query.get(current_user_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404

        # 3. PARSE QUERY PARAMETERS
        days = request.args.get('days', 30, type=int)
        weeks = request.args.get('weeks', 4, type=int)
        
        # Validate parameters to prevent abuse
        days = max(1, min(days, 365))  # Between 1 and 365 days
        weeks = max(1, min(weeks, 52))  # Between 1 and 52 weeks

        # 4. GATHER ALL ANALYTICS DATA
        # Call each analytics function to build comprehensive dashboard
        
        # Cash flow: Separate incoming vs outgoing money
        cash_flow = get_vendor_cash_flow(current_user_id, days=days)
        
        # Net flow: Profit/loss calculation
        net_flow = get_vendor_net_flow(current_user_id, days=days)
        
        # Top customers: Who pays this vendor most
        top_customers = get_vendor_top_customers(current_user_id, days=days, limit=10)
        
        # Largest transactions: Biggest payments received
        largest_transactions = get_vendor_largest_transactions(current_user_id, days=days, limit=10)
        
        # Outflow breakdown: Where money goes (refunds, transfers, etc.)
        outflow_breakdown = get_vendor_outflow_breakdown(current_user_id, days=days)
        
        # Spending ratio: How much vendor retains vs spends
        spending_ratio = get_vendor_spending_ratio(current_user_id, days=days)
        
        # Weekly performance: Week-by-week analysis
        weekly_performance = get_vendor_weekly_performance(current_user_id, weeks=weeks)
        
        # 5. BUILD COMPLETE DASHBOARD
        dashboard = {
            "cash_flow": cash_flow,
            "net_flow": net_flow,
            "top_customers": top_customers,
            "largest_transactions": largest_transactions,
            "outflow_breakdown": outflow_breakdown,
            "spending_ratio": spending_ratio,
            "weekly_performance": weekly_performance
        }

        # 6. RETURN STRUCTURED RESPONSE
        return jsonify({
            "message": "Vendor analytics retrieved successfully",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vendor_id": current_user_id,
            "business_name": vendor.get_display_name(),
            "analytics": dashboard
        }), 200

    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve analytics',
            'details': str(e)
        }), 500


@vendor_bp.route('/password', methods=['PUT'])
@jwt_required()
def update_password():
    """Change vendor password"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != 'vendor':
            return jsonify({'error': 'Unauthorized'}), 403
        
        vendor = Vendor.query.get(current_user_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Both current_password and new_password are required'}), 400

        # Verify current password
        if not vendor.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401

        # Validate new password
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400

        # Update password
        vendor.set_password(new_password)
        db.session.commit()

        return jsonify({'message': 'Password updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to update password',
            'details': str(e)
        }), 500