from flask import Blueprint, jsonify, request
from models import User, Transaction
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from extensions import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from utils.user_analytics_utils import (
    get_user_dashboard_summary,
    get_user_spending_summary,
    get_user_top_merchants,
    get_user_daily_trends_by_weekday,
    get_user_spending_trends,
    get_user_largest_transactions,
    get_user_weekly_spending,
    get_user_spending_insights
)


user_bp = Blueprint('user',__name__)

@user_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user's profile information"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    if claims.get('user_type') != 'user':
        return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
    
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        "message": "User profile retrieved successfully",
        "user": {
            "id": user.id,
            "name": user.name,
            "phone_number": user.phone_number,
            "email": user.email,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    }), 200


@user_bp.route('/profile', methods=["PUT"])
@jwt_required()
def update_profile():
    """Update current user's profile information"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != 'user':
            return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
        
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Update only provided fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({'error': 'Name cannot be empty'}), 400
            user.name = name
        
        if 'phone_number' in data:
            phone = data['phone_number'].strip()
            if not phone:
                return jsonify({'error': 'Phone number cannot be empty'}), 400
            # Check uniqueness (except current user)
            existing = User.query.filter(User.phone_number == phone, User.id != current_user_id).first()
            if existing:
                return jsonify({'error': 'Phone number already in use'}), 409
            user.phone_number = phone
        
        if 'email' in data:
            email = data['email'].strip()
            if not email:
                return jsonify({'error': 'Email cannot be empty'}), 400
            # Check uniqueness (except current user)
            existing = User.query.filter(User.email == email, User.id != current_user_id).first()
            if existing:
                return jsonify({'error': 'Email already in use'}), 409
            user.email = email

        db.session.commit()
        
        return jsonify({
            'message': 'User profile updated successfully',
            "user": {
                "id": user.id,
                "name": user.name,
                "phone_number": user.phone_number,
                "email": user.email,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
        }), 200
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Email or phone number already in use'}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to update user profile',
            'details': str(e)
        }), 500


@user_bp.route('/password', methods=['PUT'])
@jwt_required()
def update_password():
    """Change user password"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != 'user':
            return jsonify({'error': 'Unauthorized'}), 403
        
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify({'error': 'Both current_password and new_password are required'}), 400

        # Verify current password
        if not user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401

        # Validate new password
        if len(new_password) < 6:
            return jsonify({'error': 'New password must be at least 6 characters'}), 400

        # Update password
        user.set_password(new_password)
        db.session.commit()

        return jsonify({'message': 'Password updated successfully'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'Failed to update password',
            'details': str(e)
        }), 500
    

@user_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """Get all transactions for the current user with pagination"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    if claims.get('user_type') != 'user':
        return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Limit per_page to prevent abuse
    per_page = min(per_page, 100)
    
    # Query with pagination
    pagination = Transaction.query.filter_by(user_id=current_user_id)\
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


@user_bp.route('/transactions/<int:transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """Get specific transaction details for the current user"""
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    
    if claims.get('user_type') != 'user':
        return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
    
    # Find transaction and verify ownership
    transaction = Transaction.query.filter_by(id=transaction_id, user_id=current_user_id).first()
    if not transaction:
        return jsonify({'error': 'Transaction not found or access denied'}), 404

    return jsonify({
        "message": "Transaction retrieved successfully",
        "transaction": {
            "id": transaction.id,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "status": transaction.status.value,  # Enum to string
            "mpesa_receipt": transaction.mpesa_receipt,
            "phone": transaction.phone,
            "callback_response": transaction.callback_response,
            "initiated_at": transaction.initated_at.isoformat() if transaction.initated_at else None,
            "completed_at": transaction.completed_at.isoformat() if transaction.completed_at else None,
            "vendor_id": transaction.vendor_id,
            "qrcode_id": transaction.qrcode_id
        }
    }), 200


@user_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    """
    Get comprehensive analytics dashboard for the user.
    Includes spending summary, top merchants, daily trends, spending patterns,
    largest transactions, weekly spending, and personalized insights.
    
    Query Parameters:
    - days: Number of days for analysis (default: 30, max: 365)
    - months: Number of months for trends (default: 3, max: 12)
    - weeks: Number of weeks for weekly analysis (default: 4, max: 52)
    """
    try:
        # 1. AUTHENTICATION: Verify user identity
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        if claims.get('user_type') != 'user':
            return jsonify({'error': 'Unauthorized. Only registered users can access this endpoint'}), 403
        
        # 2. VERIFY USER EXISTS
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # 3. PARSE QUERY PARAMETERS
        days = request.args.get('days', 30, type=int)
        months = request.args.get('months', 3, type=int)
        weeks = request.args.get('weeks', 4, type=int)
        
        # Validate parameters to prevent abuse
        days = max(1, min(days, 365))  # Between 1 and 365 days
        months = max(1, min(months, 12))  # Between 1 and 12 months
        weeks = max(1, min(weeks, 52))  # Between 1 and 52 weeks

        # 4. GATHER ALL ANALYTICS DATA
        # Call each analytics function to build comprehensive dashboard
        
        # Overview: Total spending and transaction count
        overview = get_user_spending_summary(current_user_id, days=days)
        
        # Top merchants: Who user pays most (by amount & frequency)
        top_merchants = get_user_top_merchants(current_user_id, days=days, limit=10)
        
        # Daily patterns: Which weekdays user spends most
        weekday_patterns = get_user_daily_trends_by_weekday(current_user_id, days=days)
        
        # Monthly trends: Month-by-month spending breakdown
        monthly_trends = get_user_spending_trends(current_user_id, months=months)
        
        # Weekly breakdown: Week-by-week spending
        weekly_breakdown = get_user_weekly_spending(current_user_id, weeks=weeks)
        
        # Largest transactions: Biggest payments made
        largest_transactions = get_user_largest_transactions(current_user_id, days=days, limit=10)
        
        # Insights: Personalized spending insights
        insights = get_user_spending_insights(current_user_id, days=days)
        
        # 5. BUILD COMPLETE DASHBOARD
        dashboard = {
            "overview": overview,
            "top_merchants": top_merchants,
            "weekday_patterns": weekday_patterns,
            "monthly_trends": monthly_trends,
            "weekly_breakdown": weekly_breakdown,
            "largest_transactions": largest_transactions,
            "insights": insights
        }

        # 6. RETURN STRUCTURED RESPONSE
        return jsonify({
            "message": "User analytics retrieved successfully",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user_id,
            "user_name": user.name,
            "analytics": dashboard
        }), 200

    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve analytics',
            'details': str(e)
        }), 500

