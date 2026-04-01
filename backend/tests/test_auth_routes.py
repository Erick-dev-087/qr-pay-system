from models import User, Vendor


def _user_payload():
    return {
        'name': 'Auth User',
        'phone_number': '254700100001',
        'email': 'auth.user@example.com',
        'password': 'password123',
    }


def _vendor_payload():
    return {
        'name': 'Auth Vendor',
        'business_shortcode': 'AUTH001',
        'merchant_id': 'MERCH-AUTH',
        'mcc': '5812',
        'store_label': 'HQ',
        'email': 'auth.vendor@example.com',
        'phone': '254700100002',
        'password': 'vendorpass123',
    }


def test_register_user_success(client):
    response = client.post('/api/auth/register/user', json=_user_payload())
    data = response.get_json()

    assert response.status_code == 201
    assert data['user']['email'] == 'auth.user@example.com'
    assert 'access_token' in data


def test_register_user_missing_field(client):
    payload = _user_payload()
    payload.pop('email')

    response = client.post('/api/auth/register/user', json=payload)

    assert response.status_code == 400


def test_register_user_duplicate_email(client):
    client.post('/api/auth/register/user', json=_user_payload())
    payload2 = _user_payload()
    payload2['phone_number'] = '254700100099'

    response = client.post('/api/auth/register/user', json=payload2)

    assert response.status_code == 409


def test_register_vendor_success(client):
    response = client.post('/api/auth/register/vendor', json=_vendor_payload())
    data = response.get_json()

    assert response.status_code == 201
    assert data['vendor']['business_shortcode'] == 'AUTH001'
    assert 'access_token' in data


def test_login_user_success(client):
    client.post('/api/auth/register/user', json=_user_payload())

    response = client.post(
        '/api/auth/login',
        json={'email': 'auth.user@example.com', 'password': 'password123'},
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data['user_type'] == 'user'


def test_login_invalid_credentials(client):
    response = client.post(
        '/api/auth/login',
        json={'email': 'missing@example.com', 'password': 'wrongpass'},
    )

    assert response.status_code == 401


def test_logout_requires_auth(client):
    response = client.post('/api/auth/logout')

    assert response.status_code == 401


def test_logout_success(client, make_user, auth_header):
    user_id = make_user(email='logout.user@example.com', phone='254700100010')

    response = client.post('/api/auth/logout', headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['message'] == 'Logged out successfully'
