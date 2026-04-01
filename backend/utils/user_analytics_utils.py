from decimal import Decimal
from sqlalchemy import func, desc, asc, text
from datetime import datetime, timedelta, timezone
from models import Transaction, TransactionStatus, TransactionType, Vendor
from extensions import db


def _to_decimal(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))

# PostgreSQL date extraction helpers
def pg_weekday(col):
    """Extract weekday (0=Monday to 6=Sunday in PostgreSQL)"""
    return func.extract('DOW', col) - 1  # Convert from PostgreSQL (0=Sunday) to standard (0=Monday)

def pg_month(col):
    """Extract year-month as YYYY-MM"""
    return func.to_char(col, 'YYYY-MM')

def pg_year_week(col):
    """Extract year-week as YYYY-WW"""
    return func.to_char(col, 'YYYY-WW')

def get_user_spending_summary(user_id,days=30):
   """
   Return the cumulative sum and count of all  Users Transaction
   
   """
   end = datetime.now(timezone.utc)
   start = end - timedelta(days=days)
   q = db.session.query(
       func.coalesce(func.sum(Transaction.amount), 0).label("total"),
       func.count(Transaction.id).label("count")
   ). filter(
       Transaction.user_id == user_id,
       Transaction.status == TransactionStatus.SUCCESS
   ).one()

   row = q
   avg =  _to_decimal(row.total) / row.count if row.count > 0 else Decimal("0.00")
   return {
       "Period_days": days,
       "total_spent": str(_to_decimal(row.total)),
       "transaction_count": int(row.count),
       "average_transaction": str(round(avg, 2))

   }
   


def get_user_top_merchants(user_id, days=30, limit=10):
    """
    Find vendors user spends most with and most frequently.
    Returns business name and category instead of just vendor name.
    
    Args:
        user_id: The user's ID
        days: Number of days to look back (default 30)
        limit: Max number of results to return (default 10)
    
    Returns:
        Dict with top_by_amount and top_by_frequency lists
    """

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Query transactions grouped by vendor, with totals and counts
    q = (
        db.session.query(
            Transaction.vendor_id,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count"),  # Fixed: added missing comma
            func.max(Transaction.completed_at).label("last_transaction")  # Fixed: lebel -> label
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,  # Fixed: = -> ==
            Transaction.completed_at >= start
        )
        .group_by(Transaction.vendor_id)  # Fixed: venor_id -> vendor_id
        .all()
    )

    vendors = []
    for row in q:
        # Fetch the vendor from database using the vendor_id
        vendor = db.session.query(Vendor).filter(Vendor.id == row.vendor_id).first()  # Fixed: Vendor(id) -> query
        
        if vendor:  # Make sure vendor exists
            vendors.append({
                "business_name": vendor.get_display_name(),  # Use business_name with fallback
                "category": vendor.get_category(),  # Get category from MCC
                "total": str(_to_decimal(row.total)),
                "count": int(row.count),
                "last_transaction": row.last_transaction.strftime("%Y-%m-%d") if row.last_transaction else "N/A"
            })

    # Sort by total amount spent
    top_by_amount = sorted(
        vendors,
        key=lambda x: _to_decimal(x["total"]),
        reverse=True
    )[:limit]

    # Sort by frequency of transactions
    top_by_frequency = sorted(
        vendors,
        key=lambda x: x["count"],
        reverse=True
    )[:limit]

    return {
        "period_days": days,
        "top_by_amount": top_by_amount,
        "top_by_frequency": top_by_frequency
    }
    


def get_user_daily_trends_by_weekday(user_id, days=30):
    """
    Analyze user spending patterns by day of the week.
    Shows which days user spends most (e.g., more on weekends vs weekdays).
    
    Args:
        user_id: The user's ID
        days: Number of days to look back (default 30)
    
    Returns:
        Dict with spending totals and averages for each day of week
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Query transactions grouped by weekday (0=Monday, 6=Sunday)
    q = (
        db.session.query(
            pg_weekday(Transaction.completed_at).label('weekday'),
            func.coalesce(func.sum(Transaction.amount), 0).label('total'),
            func.count(Transaction.id).label('count')
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by(pg_weekday(Transaction.completed_at))
        .all()
    )

    # Map weekday numbers to names (SQLite %w: 0=Sunday, 1=Monday, etc.)
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Initialize all days with zero values
    results = {day: {"total": "0.00", "count": 0, "average": "0.00"} for day in day_names}
    
    # Fill in actual data
    for row in q:
        day_index = int(row.weekday)
        day_name = day_names[day_index]
        total = _to_decimal(row.total)
        count = int(row.count)
        avg = total / count if count > 0 else Decimal("0.00")
        
        results[day_name] = {
            "total": str(total),
            "count": count,
            "average": str(round(avg, 2))
        }
    
    return {
        "period_days": days,
        "by_weekday": results
    }

def get_user_spending_trends(user_id, months=3):
    """
    Show user spending trends over time (month by month).
    Helps identify if spending is increasing, decreasing, or stable.
    
    Args:
        user_id: The user's ID
        months: Number of months to look back (default 3)
    
    Returns:
        Dict with monthly spending totals and trends
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=months * 30)  # Approximate months as 30 days

    # Query transactions grouped by month
    q = (
        db.session.query(
            pg_month(Transaction.completed_at).label('month'),
            func.coalesce(func.sum(Transaction.amount), 0).label('total'),
            func.count(Transaction.id).label('count')
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by(pg_month(Transaction.completed_at))
        .order_by(pg_month(Transaction.completed_at))
        .all()
    )

    monthly_data = []
    for row in q:
        total = _to_decimal(row.total)
        count = int(row.count)
        avg = total / count if count > 0 else Decimal("0.00")
        
        monthly_data.append({
            "month": row.month,
            "total": str(total),
            "count": count,
            "average": str(round(avg, 2))
        })
    
    # Calculate trend (comparing first and last month)
    trend = "stable"
    if len(monthly_data) >= 2:
        first_month_total = _to_decimal(monthly_data[0]["total"])
        last_month_total = _to_decimal(monthly_data[-1]["total"])
        
        if last_month_total > first_month_total * Decimal("1.1"):  # 10% increase
            trend = "increasing"
        elif last_month_total < first_month_total * Decimal("0.9"):  # 10% decrease
            trend = "decreasing"
    
    return {
        "period_months": months,
        "monthly_breakdown": monthly_data,
        "trend": trend
    }

def get_user_largest_transactions(user_id, days=30, limit=10):
    """
    Get user's largest transactions (highest amounts paid).
    Useful for identifying major expenses.
    
    Args:
        user_id: The user's ID
        days: Number of days to look back (default 30)
        limit: Max number of transactions to return (default 10)
    
    Returns:
        List of largest transactions with vendor info
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Query largest transactions
    q = (
        db.session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .order_by(desc(Transaction.amount))  # Sort by amount descending
        .limit(limit)
        .all()
    )

    transactions = []
    for txn in q:
        vendor = db.session.query(Vendor).filter(Vendor.id == txn.vendor_id).first()
        
        transactions.append({
            "amount": str(_to_decimal(txn.amount)),
            "business_name": vendor.get_display_name() if vendor else "Unknown",
            "category": vendor.get_category() if vendor else "Other",
            "date": txn.completed_at.strftime("%Y-%m-%d %H:%M") if txn.completed_at else "N/A",
            "transaction_id": txn.id
        })
    
    return {
        "period_days": days,
        "largest_transactions": transactions
    }

def get_user_weekly_spending(user_id, weeks=4):
    """
    Show user spending broken down by week.
    Helps track weekly spending habits and budgets.
    
    Args:
        user_id: The user's ID
        weeks: Number of weeks to look back (default 4)
    
    Returns:
        Dict with weekly spending totals
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(weeks=weeks)

    # Query transactions grouped by week
    q = (
        db.session.query(
            pg_year_week(Transaction.completed_at).label('week'),
            func.coalesce(func.sum(Transaction.amount), 0).label('total'),
            func.count(Transaction.id).label('count')
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by(pg_year_week(Transaction.completed_at))
        .order_by(pg_year_week(Transaction.completed_at))
        .all()
    )

    weekly_data = []
    for row in q:
        total = _to_decimal(row.total)
        count = int(row.count)
        avg = total / count if count > 0 else Decimal("0.00")
        
        weekly_data.append({
            "week": row.week,
            "total": str(total),
            "count": count,
            "average": str(round(avg, 2))
        })
    
    # Calculate average weekly spending
    total_spent = sum(_to_decimal(w["total"]) for w in weekly_data)
    avg_weekly = total_spent / len(weekly_data) if weekly_data else Decimal("0.00")
    
    return {
        "period_weeks": weeks,
        "weekly_breakdown": weekly_data,
        "average_weekly_spending": str(round(avg_weekly, 2))
    }

def get_user_spending_insights(user_id, days=30):
    """
    Generate insights about user's spending patterns.
    Includes top category, peak spending day, and spending velocity.
    
    Args:
        user_id: The user's ID
        days: Number of days to analyze (default 30)
    
    Returns:
        Dict with various spending insights
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Get all successful transactions in the period
    transactions = (
        db.session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.OUTGOING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .all()
    )

    if not transactions:
        return {
            "period_days": days,
            "total_transactions": 0,
            "top_category": "N/A",
            "peak_spending_day": "N/A",
            "insights": []
        }

    # Calculate category spending
    category_totals = {}
    for txn in transactions:
        vendor = db.session.query(Vendor).filter(Vendor.id == txn.vendor_id).first()
        if vendor:
            category = vendor.get_category()
            category_totals[category] = category_totals.get(category, Decimal("0")) + _to_decimal(txn.amount)
    
    # Find top category
    top_category = max(category_totals.items(), key=lambda x: x[1])[0] if category_totals else "N/A"
    
    # Find peak spending day
    day_totals = {}
    for txn in transactions:
        if txn.completed_at:
            day = txn.completed_at.strftime("%Y-%m-%d")
            day_totals[day] = day_totals.get(day, Decimal("0")) + _to_decimal(txn.amount)
    
    peak_day = max(day_totals.items(), key=lambda x: x[1])[0] if day_totals else "N/A"
    
    # Calculate spending velocity (transactions per day)
    velocity = len(transactions) / days
    
    # Generate insights
    insights = []
    if velocity > 1:
        insights.append(f"High activity: {round(velocity, 1)} transactions per day")
    
    if category_totals:
        top_category_pct = (category_totals[top_category] / sum(category_totals.values())) * 100
        insights.append(f"{round(top_category_pct, 1)}% of spending in {top_category}")
    
    return {
        "period_days": days,
        "total_transactions": len(transactions),
        "top_category": top_category,
        "top_category_amount": str(category_totals.get(top_category, Decimal("0.00"))),
        "peak_spending_day": peak_day,
        "transactions_per_day": round(velocity, 2),
        "insights": insights
    }

def get_user_dashboard_summary(user_id, days=30):
    """
    Comprehensive dashboard combining all user analytics.
    This is the main function to call for user analytics display.
    
    Args:
        user_id: The user's ID
        days: Number of days to analyze (default 30)
    
    Returns:
        Dict with all analytics combined
    """
    return {
        "overview": get_user_spending_summary(user_id, days),
        "top_merchants": get_user_top_merchants(user_id, days),
        "weekday_patterns": get_user_daily_trends_by_weekday(user_id, days),
        "largest_transactions": get_user_largest_transactions(user_id, days, limit=5),
        "insights": get_user_spending_insights(user_id, days)
    }

