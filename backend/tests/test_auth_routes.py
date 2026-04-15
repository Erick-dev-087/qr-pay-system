from models import User, Vendor


def _user_payload():
    return {
        'name': 'Auth User',
        'phone_number': '254700100004',
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
    assert data['vendor']['shortcode_type'] == 'TILL'
    assert 'access_token' in data


def test_register_vendor_paybill_success(client):
    payload = _vendor_payload()
    payload.update(
        {
            'business_shortcode': 'AUTH002',
            'email': 'auth.vendor.paybill@example.com',
            'phone': '254700100022',
            'shortcode_type': 'PAYBILL',
            'paybill_account_number': 'INV-ACCOUNT-001',
        }
    )

    response = client.post('/api/auth/register/vendor', json=payload)
    data = response.get_json()

    assert response.status_code == 201
    assert data['vendor']['shortcode_type'] == 'PAYBILL'
    assert data['vendor']['paybill_account_number'] == 'INV-ACCOUNT-001'


def test_register_vendor_rejects_invalid_shortcode_type(client):
    payload = _vendor_payload()
    payload.update(
        {
            'business_shortcode': 'AUTH003',
            'email': 'auth.vendor.invalid-type@example.com',
            'phone': '254700100033',
            'shortcode_type': 'P2P',
        }
    )

    response = client.post('/api/auth/register/vendor', json=payload)
    data = response.get_json()

    assert response.status_code == 400
    assert 'shortcode_type' in data['error']


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


def test_forgot_password_returns_generic_message(client, app, make_user):
    make_user(email='forgot.user@example.com', phone='254700100011')

    app.config['EXPOSE_RESET_TOKEN'] = False
    response = client.post('/api/auth/forgot-password', json={'email': 'forgot.user@example.com'})
    data = response.get_json()

    assert response.status_code == 200
    assert 'message' in data
    assert 'reset_token' not in data


def test_reset_password_success_flow(client, app, make_user):
    make_user(email='reset.user@example.com', phone='254700100012', password='OldPassword123')

    app.config['EXPOSE_RESET_TOKEN'] = True

    forgot_response = client.post('/api/auth/forgot-password', json={'email': 'reset.user@example.com'})
    forgot_data = forgot_response.get_json()

    assert forgot_response.status_code == 200
    assert 'reset_token' in forgot_data

    reset_response = client.post(
        '/api/auth/reset-password',
        json={
            'token': forgot_data['reset_token'],
            'new_password': 'NewPassword123',
            'confirm_password': 'NewPassword123',
        },
    )
    reset_data = reset_response.get_json()

    assert reset_response.status_code == 200
    assert reset_data['message'] == 'Password reset successful'

    login_response = client.post(
        '/api/auth/login',
        json={'email': 'reset.user@example.com', 'password': 'NewPassword123'},
    )
    login_data = login_response.get_json()

    assert login_response.status_code == 200
    assert login_data['user_type'] == 'user'
