import os
import json
import pytest

# Ensure tests use an in-memory SQLite database and a test JWT secret
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['JWT_SECRET_KEY'] = 'test-secret'

from app import create_app
from extensions import db
from models import User, Vendor, QRCode, QR_Type, QRStatus, Transaction, TransactionStatus
from flask_jwt_extended import create_access_token


@pytest.fixture(scope='module')
def test_app():
    app = create_app()
    app.config['TESTING'] = True

    # Create database tables
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(test_app):
    return test_app.test_client()


def create_user(app, name, phone, email, password):
    with app.app_context():
        user = User(name=name, phone_number=phone, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        user_id = user.id  # Extract ID before leaving context
        return user_id


def create_vendor(app, name, shortcode, phone, email):
    with app.app_context():
        vendor = Vendor(name=name, business_shortcode=shortcode, phone=phone, email=email)
        vendor.set_password('vendorpass')
        db.session.add(vendor)
        db.session.commit()
        vendor_id = vendor.id  # Extract ID before leaving context
        return vendor_id


def create_qr(app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE, payload_json=None):
    with app.app_context():
        qr = QRCode(vendor_id=vendor_id, qr_type=qr_type, status=status, payload_json=payload_json or {}, payload_data='test_payload')
        db.session.add(qr)
        db.session.commit()
        qr_id = qr.id  # Extract ID before leaving context
        return qr_id


def auth_header_for(app, identity, user_type):
    with app.app_context():
        token = create_access_token(identity=str(identity), additional_claims={'user_type': user_type})
        return {'Authorization': f'Bearer {token}'}


def test_user_can_initiate_payment(client, test_app):
    # Arrange: create a user, vendor and QR
    user_id = create_user(test_app, 'Alice', '254712300001', 'alice@example.com', 'password123')
    vendor_id = create_vendor(test_app, 'BobShop', '174379', '254712300002', 'bob@example.com')
    qr_id = create_qr(test_app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE)

    headers = auth_header_for(test_app, user_id, 'user')
    payload = {'qr_code_id': qr_id, 'amount': 150}

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201, f"Unexpected response: {data}"
    assert 'transaction_id' in data
    assert data['amount'] == 150


def test_vendor_cannot_pay_self(client, test_app):
    # Arrange: create a vendor and a QR belonging to same vendor
    vendor_id = create_vendor(test_app, 'SelfPay', '123456', '254712300010', 'self@example.com')
    qr_id = create_qr(test_app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE)

    headers = auth_header_for(test_app, vendor_id, 'vendor')
    payload = {'qr_code_id': qr_id, 'amount': 200}

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 400
    assert data.get('message') == 'Vendors cannot pay themselves'


def test_inactive_qr_rejected(client, test_app):
    # Arrange: create user, vendor and an inactive QR
    user_id = create_user(test_app, 'Charlie', '254712300020', 'charlie@example.com', 'pass123')
    vendor_id = create_vendor(test_app, 'InactiveShop', '654321', '254712300021', 'inactive@example.com')
    qr_id = create_qr(test_app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.INACTIVE)

    headers = auth_header_for(test_app, user_id, 'user')
    payload = {'qr_code_id': qr_id, 'amount': 50}

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 400
    assert data.get('error') == 'Inactive QR Code'


# ===== NEW TESTS =====

def test_dynamic_qr_with_preset_amount(client, test_app):
    """Test payment with dynamic QR code that has a preset amount"""
    # Arrange: create user, vendor and dynamic QR with preset amount
    user_id = create_user(test_app, 'David', '254712300030', 'david@example.com', 'pass123')
    vendor_id = create_vendor(test_app, 'CoffeeShop', '987654', '254712300031', 'coffee@example.com')
    
    # Dynamic QR with preset amount in payload_json
    qr_id = create_qr(
        test_app, 
        vendor_id, 
        qr_type=QR_Type.DYNAMIC, 
        status=QRStatus.ACTIVE,
        payload_json={'amount': 250}  # Preset amount for coffee
    )

    headers = auth_header_for(test_app, user_id, 'user')
    # User doesn't provide amount - should use QR's preset amount
    payload = {'qr_code_id': qr_id}

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201, f"Unexpected response: {data}"
    assert 'transaction_id' in data
    assert data['amount'] == 250  # Should use preset amount from QR


def test_invalid_qr_code_id(client, test_app):
    """Test payment with non-existent QR code ID"""
    # Arrange: create a user but use invalid QR ID
    user_id = create_user(test_app, 'Emma', '254712300040', 'emma@example.com', 'pass123')
    
    headers = auth_header_for(test_app, user_id, 'user')
    payload = {'qr_code_id': 99999, 'amount': 100}  # Non-existent QR ID

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 404
    assert data.get('error') == 'QR code not found'


def test_vendor_can_pay_another_vendor(client, test_app):
    """Test that a vendor can pay another vendor (not themselves)"""
    # Arrange: create two different vendors
    vendor1_id = create_vendor(test_app, 'Restaurant', '111111', '254712300050', 'restaurant@example.com')
    vendor2_id = create_vendor(test_app, 'Supplier', '222222', '254712300051', 'supplier@example.com')
    
    # Create QR for vendor2 (supplier)
    qr_id = create_qr(test_app, vendor2_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE)

    # Vendor1 (restaurant) paying vendor2 (supplier)
    headers = auth_header_for(test_app, vendor1_id, 'vendor')
    payload = {'qr_code_id': qr_id, 'amount': 5000}

    # Act
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()

    # Assert
    assert resp.status_code == 201, f"Unexpected response: {data}"
    assert 'transaction_id' in data
    assert data['amount'] == 5000
    assert data['vendor']['business_shortcode'] == '222222'


def test_mpesa_callback_success(client, test_app):
    """Test successful M-Pesa callback updates transaction to SUCCESS"""
    # Arrange: create a transaction first
    user_id = create_user(test_app, 'Frank', '254712300060', 'frank@example.com', 'pass123')
    vendor_id = create_vendor(test_app, 'GasStation', '333333', '254712300061', 'gas@example.com')
    qr_id = create_qr(test_app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE)
    
    # Initiate payment to get transaction ID
    headers = auth_header_for(test_app, user_id, 'user')
    payload = {'qr_code_id': qr_id, 'amount': 1000}
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()
    transaction_id = data['transaction_id']
    checkout_request_id = data['checkout_request_id']
    
    # Simulate M-Pesa success callback
    callback_payload = {
        'Body': {
            'stkCallback': {
                'MerchantRequestID': f'MR_{transaction_id}',
                'CheckoutRequestID': checkout_request_id,
                'ResultCode': 0,
                'ResultDesc': 'The service request is processed successfully.',
                'CallbackMetadata': {
                    'Item': [
                        {'Name': 'Amount', 'Value': 1000},
                        {'Name': 'MpesaReceiptNumber', 'Value': f'QGK{transaction_id}ABC'},
                        {'Name': 'TransactionDate', 'Value': 20251105120000},
                        {'Name': 'PhoneNumber', 'Value': 254712300060}
                    ]
                }
            }
        }
    }
    
    # Act
    resp = client.post('/api/payment/confirm', json=callback_payload)
    data = resp.get_json()
    
    # Assert callback response
    assert resp.status_code == 200
    assert data['ResultCode'] == 0
    
    # Verify transaction status updated
    with test_app.app_context():
        transaction = Transaction.query.get(transaction_id)
        assert transaction.status == TransactionStatus.SUCCESS
        assert transaction.mpesa_receipt == f'QGK{transaction_id}ABC'
        assert transaction.callback_response is not None


def test_mpesa_callback_failure(client, test_app):
    """Test failed M-Pesa callback updates transaction to FAILED"""
    # Arrange: create a transaction
    user_id = create_user(test_app, 'Grace', '254712300070', 'grace@example.com', 'pass123')
    vendor_id = create_vendor(test_app, 'Pharmacy', '444444', '254712300071', 'pharmacy@example.com')
    qr_id = create_qr(test_app, vendor_id, qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE)
    
    # Initiate payment
    headers = auth_header_for(test_app, user_id, 'user')
    payload = {'qr_code_id': qr_id, 'amount': 500}
    resp = client.post('/api/payment/initiate', json=payload, headers=headers)
    data = resp.get_json()
    transaction_id = data['transaction_id']
    checkout_request_id = data['checkout_request_id']
    
    # Simulate M-Pesa failure callback (user cancelled)
    callback_payload = {
        'Body': {
            'stkCallback': {
                'MerchantRequestID': f'MR_{transaction_id}',
                'CheckoutRequestID': checkout_request_id,
                'ResultCode': 1032,
                'ResultDesc': 'Request cancelled by user'
            }
        }
    }
    
    # Act
    resp = client.post('/api/payment/confirm', json=callback_payload)
    data = resp.get_json()
    
    # Assert
    assert resp.status_code == 200
    assert data['ResultCode'] == 0  # Callback processed successfully
    
    # Verify transaction marked as FAILED
    with test_app.app_context():
        transaction = Transaction.query.get(transaction_id)
        assert transaction.status == TransactionStatus.FAILED
        assert transaction.callback_response is not None

