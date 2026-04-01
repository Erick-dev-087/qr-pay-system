import routes.vendor_routes as vendor_routes_module

from extensions import db
from models import Transaction, TransactionStatus


def test_vendor_profile_success(client, make_vendor, auth_header):
    vendor_id = make_vendor()

    response = client.get('/api/merchant/profile', headers=auth_header(vendor_id, 'vendor'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['vendor']['id'] == vendor_id


def test_vendor_profile_rejects_user_token(client, make_user, auth_header):
    user_id = make_user()

    response = client.get('/api/merchant/profile', headers=auth_header(user_id, 'user'))

    assert response.status_code == 403


def test_vendor_update_profile_success(client, make_vendor, auth_header):
    vendor_id = make_vendor(name='Old Vendor', shortcode='VEN001', email='ven1@example.com', phone='254700200001')

    response = client.put(
        '/api/merchant/profile',
        json={'name': 'New Vendor Name', 'phone': '254700299999', 'email': 'ven1.new@example.com'},
        headers=auth_header(vendor_id, 'vendor'),
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data['vendor']['name'] == 'New Vendor Name'


def test_vendor_update_profile_duplicate_shortcode_conflict(client, make_vendor, auth_header):
    vendor_a = make_vendor(name='A', shortcode='VENA01', email='a.vendor@example.com', phone='254700210001')
    make_vendor(name='B', shortcode='VENB01', email='b.vendor@example.com', phone='254700210002')

    response = client.put(
        '/api/merchant/profile',
        json={'business_shortcode': 'VENB01'},
        headers=auth_header(vendor_a, 'vendor'),
    )

    assert response.status_code == 409


def test_vendor_update_password_success(client, make_vendor, auth_header):
    vendor_id = make_vendor(password='oldvendor123')

    response = client.put(
        '/api/merchant/password',
        json={'current_password': 'oldvendor123', 'new_password': 'newvendor123'},
        headers=auth_header(vendor_id, 'vendor'),
    )

    assert response.status_code == 200


def test_vendor_transactions_only_self(app, client, make_vendor, make_user, make_qr, auth_header):
    vendor_a = make_vendor(name='Vendor A', shortcode='VA001', email='va@example.com', phone='254700220001')
    vendor_b = make_vendor(name='Vendor B', shortcode='VB001', email='vb@example.com', phone='254700220002')
    user_id = make_user()
    qr_a = make_qr(vendor_a, payload='PAY-A')
    qr_b = make_qr(vendor_b, payload='PAY-B')

    with app.app_context():
        db.session.add_all(
            [
                Transaction(
                    amount=100,
                    status=TransactionStatus.SUCCESS,
                    phone='254700220010',
                    user_id=user_id,
                    vendor_id=vendor_a,
                    qrcode_id=qr_a,
                ),
                Transaction(
                    amount=300,
                    status=TransactionStatus.SUCCESS,
                    phone='254700220011',
                    user_id=user_id,
                    vendor_id=vendor_b,
                    qrcode_id=qr_b,
                ),
            ]
        )
        db.session.commit()

    response = client.get('/api/merchant/transactions', headers=auth_header(vendor_a, 'vendor'))
    data = response.get_json()

    assert response.status_code == 200
    assert len(data['transactions']) == 1
    assert data['transactions'][0]['amount'] == 100


def test_vendor_get_single_transaction_denies_non_owner(app, client, make_vendor, make_user, make_qr, auth_header):
    owner_vendor = make_vendor(name='Owner Vendor', shortcode='OWN001', email='owner.ven@example.com', phone='254700230001')
    other_vendor = make_vendor(name='Other Vendor', shortcode='OTH001', email='other.ven@example.com', phone='254700230002')
    user_id = make_user(phone='254700230099', email='txn.user@example.com')
    qr_id = make_qr(owner_vendor, payload='PAY-OWNER')

    with app.app_context():
        tx = Transaction(
            amount=450,
            status=TransactionStatus.PENDING,
            phone='254700230099',
            user_id=user_id,
            vendor_id=owner_vendor,
            qrcode_id=qr_id,
        )
        db.session.add(tx)
        db.session.commit()
        tx_id = tx.id

    response = client.get(
        f'/api/merchant/transactions/{tx_id}',
        headers=auth_header(other_vendor, 'vendor'),
    )

    assert response.status_code == 404


def test_vendor_analytics_success(client, make_vendor, auth_header, monkeypatch):
    vendor_id = make_vendor(name='Analytics Vendor', shortcode='ANV001', email='anv@example.com', phone='254700240001')

    monkeypatch.setattr(vendor_routes_module, 'get_vendor_cash_flow', lambda *_args, **_kwargs: {'incoming': 1000, 'outgoing': 200})
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_net_flow', lambda *_args, **_kwargs: {'net': 800})
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_top_customers', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_largest_transactions', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_outflow_breakdown', lambda *_args, **_kwargs: [])
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_spending_ratio', lambda *_args, **_kwargs: {'ratio': 0.2})
    monkeypatch.setattr(vendor_routes_module, 'get_vendor_weekly_performance', lambda *_args, **_kwargs: [])

    response = client.get('/api/merchant/analytics?days=7&weeks=2', headers=auth_header(vendor_id, 'vendor'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['analytics']['net_flow']['net'] == 800
