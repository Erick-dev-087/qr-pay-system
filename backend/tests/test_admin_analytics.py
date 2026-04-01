"""
Quick test script for admin analytics functions.
Run this to see if the analytics work before testing via HTTP.
"""

from app import create_app
from utils.admin_analytics import *

# Create app context
app = create_app()

with app.app_context():
    print("="*70)
    print("🧪 TESTING ADMIN ANALYTICS")
    print("="*70)
    
    # Test 1: Active vendors count
    print("\n1️⃣ Testing get_active_vendors():")
    vendor_count = get_active_vendors()
    print(f"   ✅ Total vendors: {vendor_count}")
    
    # Test 2: Top vendors by transaction count
    print("\n2️⃣ Testing get_top_vendors_by_transaction_count():")
    top_vendors = get_top_vendors_by_transaction_count_amount(limit=3)
    for i, v in enumerate(top_vendors, 1):
        print(f"   {i}. {v['vendor_name']} ({v['business_name']}): {v['transaction_count']} transactions")
    
    # Test 3: Vendors by success rate
    print("\n3️⃣ Testing get_vendors_by_success_rate():")
    success_vendors = get_vendors_by_success_rate(limit=3, min_transactions=5)
    for i, v in enumerate(success_vendors, 1):
        print(f"   {i}. {v['vendor_name']}: {v['success_rate']}% success ({v['success_count']}/{v['total_transactions']})")
    
    # Test 4: User growth
    print("\n4️⃣ Testing get_user_growth_over_time():")
    growth = get_user_growth_over_time(days=7)
    print(f"   Last 7 days growth: {len(growth)} data points")
    for g in growth[:3]:  # Show first 3
        print(f"   - {g['date']}: {g['new_users']} new users")
    
    # Test 5: Total users
    print("\n5️⃣ Testing get_total_users():")
    user_count = get_total_users()
    print(f"   ✅ Total users: {user_count}")
    
    # Test 6: Top users by spending
    print("\n6️⃣ Testing get_top_users_by_spending():")
    top_spenders = get_top_users_by_spending(limit=3)
    for i, u in enumerate(top_spenders, 1):
        print(f"   {i}. {u['user_name']}: KES {u['total_spent']} ({u['transaction_count']} txns)")
    
    # Test 7: Complete dashboard
    print("\n7️⃣ Testing get_admin_dashboard_summary():")
    dashboard = get_admin_dashboard_summary(days=30)
    print(f"   ✅ Dashboard has {len(dashboard)} sections:")
    for section in dashboard.keys():
        print(f"      - {section}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED!")
    print("="*70)
    print("\n💡 Now test the HTTP endpoints in test_analytics.http!")
