from decimal import Decimal
from sqlalchemy import func, desc, asc, text
from datetime import datetime, timedelta, timezone
from models import Transaction, TransactionStatus, TransactionType, OutflowReason
from extensions import db
import hashlib
import os


# Helper to ensure Decimal
def _to_decimal(value):
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value))

# PostgreSQL date extraction helpers
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
def get_cumulative_total(vendor_id, start_date=None, end_date=None):
    """
    Return cumulative sum and count for a vendor between start_date and end_date.
    If dates are None, return all-time totals.
    """
    q = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.status == TransactionStatus.SUCCESS  # Use Enum, not string
    )

    if start_date:
        q = q.filter(Transaction.completed_at >= start_date)
    if end_date:
        q = q.filter(Transaction.completed_at <= end_date)

    row = q.one()
    return {
        "total": str(_to_decimal(row.total)),
        "count": int(row.count)
    }


def get_monthly_trends(vendor_id, months=6):
    """
    Return monthly totals for the last `months` months, ordered oldest to newest.
    Uses PostgreSQL date_trunc and to_char.
    """
    end = datetime.now(timezone.utc)
    start = (end - timedelta(days=months * 30)).replace(day=1)  # Approximate months back

    # Group by year-month (PostgreSQL syntax)
    group_label = pg_month(Transaction.completed_at)
    q = (
        db.session.query(
            group_label.label("month"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by("month")
        .order_by("month")
    )

    results = []
    for r in q:
        results.append({
            "month": r.month, 
            "total": str(_to_decimal(r.total)), 
            "count": int(r.count)
        })
    return results


def get_best_worst_days(vendor_id, days=30, top_n=3):
    """
    Return top N best and worst performing days by total in the last `days` days.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    day_label = pg_day(Transaction.completed_at)
    q = (
        db.session.query(
            day_label.label("day"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by("day")
        .order_by(desc("total"))
    )

    rows = q.all()
    best = [{"day": r.day, "total": str(_to_decimal(r.total)), "count": int(r.count)} for r in rows[:top_n]]
    
    # Get worst days (lowest totals, but still had transactions)
    worst_rows = sorted(rows, key=lambda x: _to_decimal(x.total))[:top_n] if rows else []
    worst = [{"day": r.day, "total": str(_to_decimal(r.total)), "count": int(r.count)} for r in worst_rows]
    
    return {"best_days": best, "worst_days": worst}


def get_kpis(vendor_id, days=30):
    """
    Return a KPI set: total last X days, average transaction, success_rate.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Total transactions (all statuses) in period
    total_row = db.session.query(
        func.count(Transaction.id).label("count"),
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.completed_at >= start
    ).one()

    # Successful transactions only
    success_row = db.session.query(
        func.count(Transaction.id).label("count"),
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.completed_at >= start,
        Transaction.status == TransactionStatus.SUCCESS
    ).one()

    total_count = int(total_row.count)
    success_count = int(success_row.count)
    success_total = _to_decimal(success_row.total)

    avg = (success_total / success_count) if success_count > 0 else Decimal("0.00")
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0.0

    return {
        "period_days": days,
        "total_revenue": str(success_total),
        "total_transactions": total_count,
        "successful_transactions": success_count,
        "average_transaction": str(round(avg, 2)),
        "success_rate_percent": round(success_rate, 2)
    }


def get_hourly_distribution(vendor_id, days=30):
    """
    Return transaction distribution by hour of day (0-23).
    Useful for understanding peak business hours.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    hour_label = pg_hour(Transaction.completed_at)
    q = (
        db.session.query(
            hour_label.label("hour"),
            func.count(Transaction.id).label("count"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by("hour")
        .order_by("hour")
    )

    results = []
    for r in q:
        results.append({
            "hour": int(r.hour),
            "count": int(r.count),
            "total": str(_to_decimal(r.total))
        })
    return results


def get_transaction_status_breakdown(vendor_id, days=30):
    """
    Return count of transactions by status (success, failed, pending, cancelled).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    q = (
        db.session.query(
            Transaction.status,
            func.count(Transaction.id).label("count")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.completed_at >= start
        )
        .group_by(Transaction.status)
    )

    results = {}
    for r in q:
        results[r.status.value] = int(r.count)
    
    # Ensure all statuses are present
    for status in TransactionStatus:
        if status.value not in results:
            results[status.value] = 0
    
    return results

def get_vendor_cash_flow(vendor_id, days=30):
    """
   Returns the cash flows of the vendors the incoming and outgoing transactions.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    incoming  = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.INCOMING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    outgoing = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    total_in = _to_decimal(incoming.total)
    total_out = _to_decimal(outgoing.total)
    net_flow = total_in - total_out

    return {
        "period_days": days,
        "total_in": str(total_in),
        "total_out": str(total_out),
        "net_flow": str(net_flow),
        "in_count": int(incoming.count),
        "out_count": int(outgoing.count)
    }


def get_vendor_net_flow(vendor_id, days=30):
    """
    Calculates the net position (profit/loss from transactions)

    """

    end = datetime.now(timezone.utc)
    start = (end  - timedelta(days=days))

    incoming  = db.session.query(

        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.INCOMING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at>= start
    ).one()

    outgoing = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    total_in = _to_decimal(incoming.total)
    total_out = _to_decimal(outgoing.total)
    net_flow = total_in - total_out

    # Fixed logic: Negative net_flow = Deficit, Positive = Surplus
    if net_flow < 0:
        status = "deficit"
    else:
        status = "surplus"

    # Calculate percentage safely (avoid division by zero)
    percentage = round((total_in / total_out * 100), 2) if total_out > 0 else 0.0

    return {
        "period_days": days,
        "net_revenue": str(net_flow),
        "status": status,
        "percentage": percentage
    }



def get_vendor_top_customers(vendor_id, days=30, limit=10):
    """
    Find customers who paid the most or most frequently.
    Returns anonymized customer data compliant with Kenya Data Protection Act.
    """
    
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    
    q = (
        db.session.query(
            Transaction.user_id,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count"),
            func.max(Transaction.completed_at).label("last_transaction")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.type == TransactionType.INCOMING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by(Transaction.user_id)
        .all()
    )

    customers = []
    for row in q:
        # Generate anonymized customer ID
        customer_id = _hash_customer_id(row.user_id, vendor_id)
        
        customers.append({
            "customer_id": customer_id,
            "total": str(_to_decimal(row.total)),
            "count": int(row.count),
            "avg_transaction": str(_to_decimal(row.total / row.count)) if row.count > 0 else "0.00",
            "last_transaction": row.last_transaction.strftime("%Y-%m-%d"),
            
        })

    # Sort by amount (descending)
    top_by_amount = sorted(
        customers, 
        key=lambda x: _to_decimal(x["total"]), 
        reverse=True
    )[:limit]

    # Sort by frequency (descending)
    top_by_frequency = sorted(
        customers, 
        key=lambda x: x["count"], 
        reverse=True
    )[:limit]

    return {
        "top_by_amount": top_by_amount,
        "top_by_frequency": top_by_frequency
    }


def _hash_customer_id(user_id, vendor_id):
    """
    Generate consistent anonymized customer ID starting with 'CUST'.
    Same customer always gets same ID for a vendor, but cannot be reversed.
    """
    # Get secret key from environment (set this in your .env file)
    secret = os.getenv('CUSTOMER_HASH_SECRET')
    
    # Create hash input combining secret, user_id, and vendor_id
    hash_input = f"{secret}:{user_id}:{vendor_id}".encode('utf-8')
    
    # Generate SHA256 hash and take first 8 characters
    hash_output = hashlib.sha256(hash_input).hexdigest()[:8].upper()
    
    return f"CUST{hash_output}"

def get_vendor_largest_transactions(vendor_id, days=30, limit=10):
    """
    Show the biggest individual payments received (not grouped, actual transactions).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    
    # Query: Get individual transactions (NOT grouped)
    q = (
        db.session.query(
            Transaction.id,
            Transaction.user_id,
            Transaction.amount,
            Transaction.completed_at,
            Transaction.status
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.type == TransactionType.INCOMING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .order_by(desc(Transaction.amount))  # Sort by amount (highest first)
        .limit(limit)  # Only get top N
        .all()
    )

    transactions = []
    for row in q:
        customer_id = _hash_customer_id(row.user_id, vendor_id)
        
        transactions.append({
            "transaction_id": row.id,
            "date": row.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
            "amount": str(_to_decimal(row.amount)),
            "customer_id": customer_id,
            "status": row.status.value
        })

    return {
        "top_transactions": transactions
    }

def get_vendor_outflow_breakdown(vendor_id, days=30):
    """
    Analyze vendor outflows broken down by reason (refunds, transfers, payouts).
    Uses OutflowReason Enum for type-safe categorization.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    # Get total incoming for percentage calculation
    incoming = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.INCOMING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    # Get total outgoing
    outgoing_total = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    # Breakdown by outflow_reason (Enum)
    breakdown_query = db.session.query(
        Transaction.outflow_reason,
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).group_by(Transaction.outflow_reason).all()

    total_in = _to_decimal(incoming.total)
    total_out = _to_decimal(outgoing_total.total)

    # Build breakdown dictionary using Enum values
    breakdown = {}
    for row in breakdown_query:
        # row.outflow_reason is an Enum, get its value
        reason_key = row.outflow_reason.value if row.outflow_reason else "unspecified"
        breakdown[reason_key] = {
            "amount": str(_to_decimal(row.total)),
            "count": int(row.count)
        }

    # Ensure all OutflowReason types are present (even if 0)
    for reason in OutflowReason:
        if reason.value not in breakdown:
            breakdown[reason.value] = {
                "amount": "0.00",
                "count": 0
            }

    # Calculate percentage safely
    outflow_percentage = round((total_out / total_in * 100), 2) if total_in > 0 else 0.0

    return {
        "period_days": days,
        "total_outflow": str(total_out),
        "outflow_percentage": outflow_percentage,
        "breakdown": breakdown  # {"refund": {"amount": "...", "count": 5}, ...}
    }


def get_vendor_spending_ratio(vendor_id, days=30):
    """
    Calculate spending ratio and retention rate for the vendor.
    Shows what percentage of incoming money is spent vs retained.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    incoming = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.INCOMING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    outgoing = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        func.count(Transaction.id).label("count")
    ).filter(
        Transaction.vendor_id == vendor_id,
        Transaction.type == TransactionType.OUTGOING,
        Transaction.status == TransactionStatus.SUCCESS,
        Transaction.completed_at >= start
    ).one()

    total_in = _to_decimal(incoming.total)
    total_out = _to_decimal(outgoing.total)
    net_flow = total_in - total_out

    # Calculate ratios safely (avoid division by zero)
    spending_ratio = round((total_out / total_in * 100), 2) if total_in > 0 else 0.0
    retention_rate = round((net_flow / total_in * 100), 2) if total_in > 0 else 0.0

    return {
        "period_days": days,
        "total_in": str(total_in),
        "total_out": str(total_out),
        "spending_ratio": spending_ratio,
        "retention_rate": retention_rate,
        "net_profit": str(net_flow)
    }

def get_vendor_weekly_performance(vendor_id, weeks=4):
    """
    Compare vendor performance week-by-week.
    Groups transactions by ISO week number.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=weeks * 7)

    # Group by ISO week
    group_label = pg_year_week(Transaction.completed_at)
    q = (
        db.session.query(
            group_label.label("week"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            func.count(Transaction.id).label("count")
        )
        .filter(
            Transaction.vendor_id == vendor_id,
            Transaction.type == TransactionType.INCOMING,
            Transaction.status == TransactionStatus.SUCCESS,
            Transaction.completed_at >= start
        )
        .group_by("week")
        .order_by("week")
    )

    results = []
    for r in q:
        avg = _to_decimal(r.total) / r.count if r.count > 0 else Decimal("0.00")
        results.append({
            "week": r.week,
            "revenue": str(_to_decimal(r.total)),
            "count": int(r.count),
            "average": str(round(avg, 2))
        })

    # Find best and worst weeks
    if results:
        best_week = max(results, key=lambda x: _to_decimal(x["revenue"]))
        worst_week = min(results, key=lambda x: _to_decimal(x["revenue"]))
    else:
        best_week = worst_week = None

    return {
        "weeks": results,
        "best_week": best_week["week"] if best_week else None,
        "worst_week": worst_week["week"] if worst_week else None
    }


def get_vendor_dashboard_summary(vendor_id, days=30):
    """
    Comprehensive dashboard summary combining all analytics in one call.
    Reduces multiple API calls - returns everything needed for vendor dashboard.
    """
    # Get all analytics data
    cash_flow = get_vendor_cash_flow(vendor_id, days)
    kpis = get_kpis(vendor_id, days)
    top_customers = get_vendor_top_customers(vendor_id, days, limit=5)
    largest_txs = get_vendor_largest_transactions(vendor_id, days, limit=5)
    best_worst = get_best_worst_days(vendor_id, days, top_n=3)
    hourly = get_hourly_distribution(vendor_id, days)
    status_breakdown = get_transaction_status_breakdown(vendor_id, days)
    spending_ratio = get_vendor_spending_ratio(vendor_id, days)
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "overview": {
            "total_in": cash_flow["total_in"],
            "total_out": cash_flow["total_out"],
            "net_flow": cash_flow["net_flow"],
            "in_count": cash_flow["in_count"],
            "out_count": cash_flow["out_count"],
            "average_transaction": kpis["average_transaction"],
            "success_rate": kpis["success_rate_percent"]
        },
        "financial_health": {
            "spending_ratio": spending_ratio["spending_ratio"],
            "retention_rate": spending_ratio["retention_rate"],
            "net_profit": spending_ratio["net_profit"]
        },
        "top_customers": {
            "by_amount": top_customers["top_by_amount"],
            "by_frequency": top_customers["top_by_frequency"]
        },
        "largest_transactions": largest_txs["top_transactions"],
        "performance": {
            "best_days": best_worst["best_days"],
            "worst_days": best_worst["worst_days"]
        },
        "distribution": {
            "by_hour": hourly,
            "by_status": status_breakdown
        }
    }


    










    