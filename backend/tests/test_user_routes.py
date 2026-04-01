import routes.user_routes as user_routes_module
from extensions import db
from models import Transaction, TransactionStatus


def test_get_profile_success(client, make_user, auth_header):
	user_id = make_user()

	response = client.get('/api/user/profile', headers=auth_header(user_id, 'user'))
	data = response.get_json()

	assert response.status_code == 200
	assert data['user']['id'] == user_id


def test_get_profile_rejects_vendor_token(client, make_vendor, auth_header):
	vendor_id = make_vendor()

	response = client.get('/api/user/profile', headers=auth_header(vendor_id, 'vendor'))

	assert response.status_code == 403


def test_update_profile_success(client, make_user, auth_header):
	user_id = make_user(name='Alice', phone='254711111111', email='alice@example.com')

	payload = {
		'name': 'Alice Updated',
		'phone_number': '254722222222',
		'email': 'alice.updated@example.com',
	}
	response = client.put('/api/user/profile', json=payload, headers=auth_header(user_id, 'user'))
	data = response.get_json()

	assert response.status_code == 200
	assert data['user']['name'] == 'Alice Updated'
	assert data['user']['email'] == 'alice.updated@example.com'


def test_update_profile_duplicate_email_conflict(client, make_user, auth_header):
	user_id = make_user(name='User A', phone='254733333331', email='a@example.com')
	make_user(name='User B', phone='254733333332', email='b@example.com')

	response = client.put(
		'/api/user/profile',
		json={'email': 'b@example.com'},
		headers=auth_header(user_id, 'user'),
	)

	assert response.status_code == 409


def test_update_password_success(client, make_user, auth_header):
	user_id = make_user(password='oldpass123')

	response = client.put(
		'/api/user/password',
		json={'current_password': 'oldpass123', 'new_password': 'newpass123'},
		headers=auth_header(user_id, 'user'),
	)

	assert response.status_code == 200
	assert response.get_json()['message'] == 'Password updated successfully'


def test_update_password_wrong_current_password(client, make_user, auth_header):
	user_id = make_user(password='oldpass123')

	response = client.put(
		'/api/user/password',
		json={'current_password': 'wrong-pass', 'new_password': 'newpass123'},
		headers=auth_header(user_id, 'user'),
	)

	assert response.status_code == 401


def test_get_transactions_returns_only_current_user_records(app, client, make_user, make_vendor, make_qr, auth_header):
	user_a = make_user(name='User A', phone='254744444441', email='ua@example.com')
	user_b = make_user(name='User B', phone='254744444442', email='ub@example.com')
	vendor_id = make_vendor()
	qr_id = make_qr(vendor_id)

	with app.app_context():
		tx1 = Transaction(
			amount=100,
			status=TransactionStatus.SUCCESS,
			phone='254744444441',
			user_id=user_a,
			vendor_id=vendor_id,
			qrcode_id=qr_id,
		)
		tx2 = Transaction(
			amount=200,
			status=TransactionStatus.PENDING,
			phone='254744444442',
			user_id=user_b,
			vendor_id=vendor_id,
			qrcode_id=qr_id,
		)
		db.session.add_all([tx1, tx2])
		db.session.commit()

	response = client.get('/api/user/transactions', headers=auth_header(user_a, 'user'))
	data = response.get_json()

	assert response.status_code == 200
	assert len(data['transactions']) == 1
	assert data['transactions'][0]['amount'] == 100


def test_get_single_transaction_denies_non_owner(app, client, make_user, make_vendor, make_qr, auth_header):
	owner_id = make_user(name='Owner', phone='254755555551', email='owner@example.com')
	other_id = make_user(name='Other', phone='254755555552', email='other@example.com')
	vendor_id = make_vendor()
	qr_id = make_qr(vendor_id)

	with app.app_context():
		tx = Transaction(
			amount=350,
			status=TransactionStatus.PENDING,
			phone='254755555551',
			user_id=owner_id,
			vendor_id=vendor_id,
			qrcode_id=qr_id,
		)
		db.session.add(tx)
		db.session.commit()
		tx_id = tx.id

	response = client.get(
		f'/api/user/transactions/{tx_id}',
		headers=auth_header(other_id, 'user'),
	)

	assert response.status_code == 404


def test_get_analytics_success_with_expected_shape(client, make_user, auth_header, monkeypatch):
	user_id = make_user(name='Analytic User', phone='254766666661', email='analytics@example.com')

	monkeypatch.setattr(user_routes_module, 'get_user_spending_summary', lambda *_args, **_kwargs: {'total_spent': 1200})
	monkeypatch.setattr(user_routes_module, 'get_user_top_merchants', lambda *_args, **_kwargs: [])
	monkeypatch.setattr(user_routes_module, 'get_user_daily_trends_by_weekday', lambda *_args, **_kwargs: [])
	monkeypatch.setattr(user_routes_module, 'get_user_spending_trends', lambda *_args, **_kwargs: [])
	monkeypatch.setattr(user_routes_module, 'get_user_weekly_spending', lambda *_args, **_kwargs: [])
	monkeypatch.setattr(user_routes_module, 'get_user_largest_transactions', lambda *_args, **_kwargs: [])
	monkeypatch.setattr(user_routes_module, 'get_user_spending_insights', lambda *_args, **_kwargs: {'tip': 'Keep saving'})

	response = client.get('/api/user/analytics?days=10&months=2&weeks=2', headers=auth_header(user_id, 'user'))
	data = response.get_json()

	assert response.status_code == 200
	assert data['analytics']['overview']['total_spent'] == 1200

