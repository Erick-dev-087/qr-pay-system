from decimal import Decimal
from sqlalchemy import func, desc, asc
from sqlalchemy import table, column, select
from datetime import datetime, timedelta,timezone
from models import Vendor, User, Transaction,TransactionType, TransactionStatus
from extensions import db
import os

def _to_decimal(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))

def pg_month(col):
    """Extract year-month as YYYY-MM"""
    return func.to_char(col, 'YYYY-MM')

def pg_day(col):
    """Extract date as YYYY-MM-DD"""
    return func.to_char(col, 'YYYY-MM-DD')

def pg_hour(col):
    """Extract hour (00-23)"""
    return func.to_char(col, 'HH24')

def pg_year_week(col):
    """Extract year-week as YYYY-WW"""
    return func.to_char(col, 'YYYY-WW')

################################################################################
# VENDOR ANALYTICS
################################################################################

def get_active_vendors():
    """
    Count how many vendors are registered in the system.
    
   
    Returns:
        int: Total number of vendors
    """
    count = db.session.query(func.count(Vendor.id)).scalar()
    return count if count else 0


def get_top_vendors_by_transaction_count_amount(limit=10):
    """
    Get vendors with the most transactions (incoming payments from customers).
    
    
    Returns:
        list: [{"vendor_id": 1, "name": "Shop A", "transaction_count": 150}, ...]
    """
    
    # Query: Join Transaction and Vendor tables
    results = db.session.query(
        Vendor.id.label("vendor_id"),
        Vendor.name.label("vendor_name"),
        Vendor.business_name.label("business_name"),
        func.sum(Transaction.amount).label("total_received"),
        func.count(Transaction.id).label("transaction_count")
    ).join(
        Transaction, Transaction.vendor_id == Vendor.id
    ).filter(
        Transaction.type == TransactionType.INCOMING  # Only customer payments
    ).group_by(
        Vendor.id, Vendor.name, Vendor.business_name
    ).order_by(
        desc("transaction_count")
    ).limit(limit).all()
    
    # Convert to list of dictionaries
    return [
        {
            "vendor_id": r.vendor_id,
            "vendor_name": r.vendor_name,
            "business_name": r.business_name,
            "transaction_amount": r.total_received,
            "transaction_count": r.transaction_count
        }
        for r in results
    ]


def get_vendors_by_success_rate(limit=10, min_transactions=5):
    """
    Get vendors with the highest transaction success rates.
    
    SQL concept:
        success_rate = (COUNT of SUCCESS transactions / COUNT of ALL transactions) * 100
    
    Returns:
        list: [{"vendor_id": 1, "name": "Shop A", "success_rate": 98.5, "total": 200}, ...]
    """
    from models import TransactionType, TransactionStatus
    from sqlalchemy import case
    
    # Count successful transactions
    success_count = func.count(
        case(
            (Transaction.status == TransactionStatus.SUCCESS, 1),
            else_=None
        )
    ).label("success_count")
    
    # Count all transactions
    total_count = func.count(Transaction.id).label("total_count")
    
    # Calculate success rate percentage
    success_rate = (
        func.cast(success_count, db.Numeric) / 
        func.cast(total_count, db.Numeric) * 100
    ).label("success_rate")
    
    results = db.session.query(
        Vendor.id.label("vendor_id"),
        Vendor.name.label("vendor_name"),
        Vendor.business_name.label("business_name"),
        success_count,
        total_count,
        success_rate
    ).join(
        Transaction, Transaction.vendor_id == Vendor.id
    ).filter(
        Transaction.type == TransactionType.INCOMING
    ).group_by(
        Vendor.id, Vendor.name, Vendor.business_name
    ).having(
        total_count >= min_transactions  # Only vendors with enough transactions
    ).order_by(
        desc("success_rate")
    ).limit(limit).all()
    
    return [
        {
            "vendor_id": r.vendor_id,
            "vendor_name": r.vendor_name,
            "business_name": r.business_name,
            "success_count": r.success_count,
            "total_transactions": r.total_count,
            "success_rate": round(float(r.success_rate), 2) if r.success_rate else 0.0
        }
        for r in results
    ]





################################################################################
# USER ANALYTICS
################################################################################

def get_user_growth_over_time(days=30):
    """
    Track how many users signed up each day/week.
    Shows if your platform is growing!
    
    LEARNING POINTS:
    1. Date grouping: Group users by the day they created_at
    2. Time filtering: Only look at last N days
    3. Ordering by date: See growth chronologically
    
    Args:
        days (int): How many days back to look
        
    Returns:
        list: [{"date": "2025-12-01", "new_users": 5}, ...]
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    results = db.session.query(
        pg_day(User.created_at).label("signup_date"),
        func.count(User.id).label("new_users")
    ).filter(
        User.created_at >= start_date
    ).group_by(
        "signup_date"
    ).order_by(
        asc("signup_date")
    ).all()
    
    return [
        {
            "date": r.signup_date,
            "new_users": r.new_users
        }
        for r in results
    ]


def get_total_users():
    """
    Simple count of all registered users.
    
    Returns:
        int: Total user count
    """
    count = db.session.query(func.count(User.id)).scalar()
    return count if count else 0


def get_top_users_by_transaction_count(limit=10):
    """
    Find users who make the most transactions (most active customers).
    
    Returns:
        list: [{"user_id": 1, "name": "John", "transaction_count": 45}, ...]
    """
    from models import TransactionType
    
    results = db.session.query(
        User.id.label("user_id"),
        User.name.label("user_name"),
        User.email.label("email"),
        func.count(Transaction.id).label("transaction_count")
    ).join(
        Transaction, Transaction.user_id == User.id
    ).filter(
        Transaction.type == TransactionType.OUTGOING  # User spending
    ).group_by(
        User.id, User.name, User.email
    ).order_by(
        desc("transaction_count")
    ).limit(limit).all()
    
    return [
        {
            "user_id": r.user_id,
            "user_name": r.user_name,
            "email": r.email,
            "transaction_count": r.transaction_count
        }
        for r in results
    ]


def get_top_users_by_spending(limit=10):
    """
    Find users who spend the MOST money (high-value customers).
    
    Returns:
        list: [{"user_id": 1, "name": "John", "total_spent": "125000.50"}, ...]
    """

    
    results = db.session.query(
        User.id.label("user_id"),
        User.name.label("user_name"),
        User.email.label("email"),
        func.sum(Transaction.amount).label("total_spent"),
        func.count(Transaction.id).label("transaction_count")
    ).join(
        Transaction, Transaction.user_id == User.id
    ).filter(
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS
    ).group_by(
        User.id, User.name, User.email
    ).order_by(
        desc("total_spent")
    ).limit(limit).all()
    
    return [
        {
            "user_id": r.user_id,
            "user_name": r.user_name,
            "email": r.email,
            "total_spent": str(_to_decimal(r.total_spent)),
            "transaction_count": r.transaction_count
        }
        for r in results
    ]


################################################################################
# DASHBOARD SUMMARY (Combines everything!)
################################################################################

def get_admin_dashboard_summary(days=30):
    """
    THE BIG ONE! Returns everything an admin needs to see.
    
    LEARNING POINT:
    - We call all the individual functions we built
    - Combine results into one big response
    - This is what your admin dashboard will display
    
    Args:
        days (int): Time period for growth metrics
        
    Returns:
        dict: Complete admin dashboard data
    """
    return {
        # Platform Overview
        "platform_stats": {
            "total_vendors": get_active_vendors(),
            "total_users": get_total_users()
        },
        
        # Vendor Insights
        "vendor_insights": {
            "top_by_volume": get_top_vendors_by_transaction_count_amount(limit=5),
            "top_by_success_rate": get_vendors_by_success_rate(limit=5, min_transactions=5)
        },
        
        # User Insights
        "user_insights": {
            "growth_chart": get_user_growth_over_time(days=days),
            "top_by_activity": get_top_users_by_transaction_count(limit=5),
            "top_by_spending": get_top_users_by_spending(limit=5)
        }
    }
 