import routes.admin_routes as admin_routes_module


def test_admin_metrics_overview_success(client, make_user, auth_header, monkeypatch):
    user_id = make_user(email='admin.metrics@example.com', phone='254700400001')

    monkeypatch.setattr(admin_routes_module, 'get_admin_dashboard_summary', lambda days=30: {'days': days, 'kpi': {'total_tx': 5}})

    response = client.get('/api/admin/api/admin/metrics/overview?days=30', headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['dashboard']['kpi']['total_tx'] == 5


def test_admin_metrics_overview_rejects_invalid_days(client, make_user, auth_header):
    user_id = make_user(email='admin.invalid@example.com', phone='254700400002')

    response = client.get('/api/admin/api/admin/metrics/overview?days=500', headers=auth_header(user_id, 'user'))

    assert response.status_code == 400


def test_admin_metrics_merchants_success(client, make_user, auth_header, monkeypatch):
    user_id = make_user(email='admin.merchants@example.com', phone='254700400003')

    monkeypatch.setattr(admin_routes_module, 'get_top_vendors_by_transaction_count_amount', lambda limit=10: [{'id': 1}])
    monkeypatch.setattr(admin_routes_module, 'get_vendors_by_success_rate', lambda limit=10, min_transactions=5: [{'id': 1, 'success_rate': 1.0}])
    monkeypatch.setattr(admin_routes_module, 'get_active_vendors', lambda: 2)

    response = client.get('/api/admin/api/admin/metrics/merchants?limit=5', headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['data']['total_merchants'] == 2


def test_admin_metrics_users_success(client, make_user, auth_header, monkeypatch):
    user_id = make_user(email='admin.users@example.com', phone='254700400004')

    monkeypatch.setattr(admin_routes_module, 'get_user_growth_over_time', lambda days=30: [{'day': '2026-01-01', 'count': 1}])
    monkeypatch.setattr(admin_routes_module, 'get_top_users_by_transaction_count', lambda limit=10: [{'user_id': 1, 'count': 3}])
    monkeypatch.setattr(admin_routes_module, 'get_top_users_by_spending', lambda limit=10: [{'user_id': 1, 'amount': 200}])
    monkeypatch.setattr(admin_routes_module, 'get_total_users', lambda: 10)

    response = client.get('/api/admin/api/admin/metrics/users?days=20&limit=5', headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['data']['total_users'] == 10


def test_admin_metrics_require_auth(client):
    response = client.get('/api/admin/api/admin/metrics/overview')

    assert response.status_code == 401
