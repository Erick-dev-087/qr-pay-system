from flask import Blueprint,jsonify, request
from models import Vendor, User, Transaction, QRCode,QRStatus,QR_Type
from extensions import db, limiter
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from utils.admin_analytics import (
    get_admin_dashboard_summary,
    get_active_vendors,
    get_top_vendors_by_transaction_count_amount,
    get_vendors_by_success_rate,
    get_user_growth_over_time,
    get_total_users,
    get_top_users_by_transaction_count,
    get_top_users_by_spending,
    get_all_vendors,
    get_all_users
)


admin_bp = Blueprint('admin',__name__)




@admin_bp.route('/api/admin/metrics/overview', methods=['GET'])
@limiter.limit('20 per minute')
@jwt_required()
def get_dashboard_overview():
    """
    GET /api/admin/metrics/overview?days=30
    
    Returns complete admin dashboard with all metrics.
    
    LEARNING POINT:
    - This calls get_admin_dashboard_summary() from admin_analytics.py
    - Returns everything in one response
    - Query param 'days' controls time period (default 30)
    """
    try:
        # TODO: Add admin role check
        # claims = get_jwt()
        # if claims.get('user_type') != 'admin':
        #     return jsonify({'error': 'Admin access required'}), 403
        
        days = request.args.get('days', default=30, type=int)
        
        if days < 1 or days > 365:
            return jsonify({'error': 'Days must be between 1 and 365'}), 400
        
        dashboard_data = get_admin_dashboard_summary(days=days)
        
        return jsonify({
            'message': 'Dashboard data retrieved successfully',
            'dashboard': dashboard_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve dashboard', 'details': str(e)}), 500


@admin_bp.route('/api/admin/metrics/merchants', methods=['GET'])
@limiter.limit('20 per minute')
@jwt_required()
def get_merchant_insights():
    """
    GET /api/admin/metrics/merchants?limit=10
    
    Returns detailed vendor/merchant analytics.
    """
    try:
        limit = request.args.get('limit', default=10, type=int)
        
        return jsonify({
            'message': 'Merchant insights retrieved',
            'data': {
                'top_by_volume': get_top_vendors_by_transaction_count_amount(limit=limit),
                'top_by_success': get_vendors_by_success_rate(limit=limit, min_transactions=5),
                'total_merchants': get_active_vendors()
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve merchant insights', 'details': str(e)}), 500


@admin_bp.route('/api/admin/metrics/users', methods=['GET'])
@limiter.limit('20 per minute')
@jwt_required()
def get_user_insights():
    """
    GET /api/admin/metrics/users?days=30&limit=10
    
    Returns detailed user analytics.
    """
    try:
        days = request.args.get('days', default=30, type=int)
        limit = request.args.get('limit', default=10, type=int)
        
        return jsonify({
            'message': 'User insights retrieved',
            'data': {
                'growth_chart': get_user_growth_over_time(days=days),
                'top_by_activity': get_top_users_by_transaction_count(limit=limit),
                'top_by_spending': get_top_users_by_spending(limit=limit),
                'total_users': get_total_users()
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve user insights', 'details': str(e)}), 500


@admin_bp.route('/api/admin/vendors/all', methods=['GET'])
@limiter.limit('15 per minute')
@jwt_required()
def get_all_vendors_endpoint():
    """
    
    """
    try:
        exclude_inactive = request.args.get('exclude_inactive', default='false', type=str).lower() == 'true'
        
        result = get_all_vendors(exclude_inactive=exclude_inactive)
        
        return jsonify({
            'message': 'All vendors retrieved',
            'total_vendors': result['total_vendors'],
            'vendors': result['vendors']
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve vendors', 'details': str(e)}), 500


@admin_bp.route('/api/admin/users/all', methods=['GET'])
@limiter.limit('15 per minute')
@jwt_required()
def get_all_users_endpoint():
    """
    GET /api/admin/users/all?exclude_inactive=false
    
    
    """
    try:
        exclude_inactive = request.args.get('exclude_inactive', default='false', type=str).lower() == 'true'
        
        result = get_all_users(exclude_inactive=exclude_inactive)
        
        return jsonify({
            'message': 'All users retrieved',
            'total_users': result['total_users'],
            'users': result['users']
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to retrieve users', 'details': str(e)}), 500
