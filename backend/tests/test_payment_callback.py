"""
Tests for M-Pesa/Daraja payment callback handling
Tests the /api/payment/confirm endpoint
"""
import pytest
from app import create_app
from extensions import db
from models import (
    User, Vendor, Transaction, QRCode, PaymentSession,
    TransactionStatus, PaymentStatus, QRStatus, QR_Type
)
from datetime import datetime


@pytest.fixture
def app():
    """Create test app with in-memory database"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['JWT_SECRET_KEY'] = 'test-secret'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()


@pytest.fixture
def sample_user(app):
    """Create a test user"""
    with app.app_context():
        user = User(
            name="Test User",
            phone_number="254712345678",
            email="testuser@example.com"
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_vendor(app):
    """Create a test vendor"""
    with app.app_context():
        vendor = Vendor(
            name="Test Vendor",
            business_shortcode="123456",
            email="vendor@example.com",
            phone="254700000000"
        )
        vendor.set_password("vendor123")
        db.session.add(vendor)
        db.session.commit()
        return vendor.id


@pytest.fixture
def sample_qr(app, sample_vendor):
    """Create a test QR code"""
    with app.app_context():
        qr = QRCode(
            payload_data="00020101021234567890",
            qr_type=QR_Type.STATIC,
            status=QRStatus.ACTIVE,
            vendor_id=sample_vendor
        )
        db.session.add(qr)
        db.session.commit()
        return qr.id


@pytest.fixture
def sample_transaction(app, sample_user, sample_vendor, sample_qr):
    """Create a pending transaction"""
    with app.app_context():
        transaction = Transaction(
            amount=100,
            status=TransactionStatus.PENDING,
            phone="254712345678",
            user_id=sample_user,
            vendor_id=sample_vendor,
            qrcode_id=sample_qr
        )
        db.session.add(transaction)
        db.session.commit()
        return transaction.id


def test_callback_success(client, app, sample_transaction, sample_user):
    """Test successful payment callback"""
    with app.app_context():
        transaction = Transaction.query.get(sample_transaction)
        
        # Simulate Daraja success callback
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_191220191020363925",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                            {"Name": "TransactionDate", "Value": 20191219102115},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }
        
        response = client.post(
            '/api/payment/confirm',
            json=callback_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['ResultCode'] == 0
        
        # Verify transaction was updated
        db.session.refresh(transaction)
        assert transaction.status == TransactionStatus.SUCCESS
        assert transaction.mpesa_receipt == "NLJ7RT61SV"
        assert transaction.callback_response is not None


def test_callback_failure(client, app, sample_transaction):
    """Test failed payment callback"""
    with app.app_context():
        transaction = Transaction.query.get(sample_transaction)
        
        # Simulate Daraja failure callback
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_191220191020363925",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "PhoneNumber", "Value": 254712345678},
                            {"Name": "Amount", "Value": 100}
                        ]
                    }
                }
            }
        }
        
        response = client.post(
            '/api/payment/confirm',
            json=callback_data,
            content_type='application/json'
        )
        
        assert response.status_code == 200
        
        # Verify transaction was marked as failed
        db.session.refresh(transaction)
        assert transaction.status == TransactionStatus.FAILED
        assert transaction.callback_response is not None


def test_callback_idempotency(client, app, sample_transaction):
    """Test that duplicate callbacks are handled correctly"""
    with app.app_context():
        transaction = Transaction.query.get(sample_transaction)
        
        callback_data = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": "ws_CO_191220191020363925",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }
        
        # First callback
        response1 = client.post('/api/payment/confirm', json=callback_data)
        assert response1.status_code == 200
        
        db.session.refresh(transaction)
        receipt_first = transaction.mpesa_receipt
        
        # Second callback (duplicate)
        response2 = client.post('/api/payment/confirm', json=callback_data)
        assert response2.status_code == 200
        
        # Transaction should not be processed again
        db.session.refresh(transaction)
        assert transaction.mpesa_receipt == receipt_first


def test_callback_missing_checkout_id(client):
    """Test callback with missing checkout request ID"""
    callback_data = {
        "Body": {
            "stkCallback": {
                "ResultCode": 0,
                "ResultDesc": "Success"
            }
        }
    }
    
    response = client.post('/api/payment/confirm', json=callback_data)
    assert response.status_code == 200  # Should acknowledge even if invalid


def test_callback_transaction_not_found(client):
    """Test callback for non-existent transaction"""
    callback_data = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_NONEXISTENT",
                "ResultCode": 0,
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 9999},
                        {"Name": "PhoneNumber", "Value": 254700000000}
                    ]
                }
            }
        }
    }
    
    response = client.post('/api/payment/confirm', json=callback_data)
    assert response.status_code == 200  # Should acknowledge


def test_callback_ping_endpoint(client):
    """Test the callback ping endpoint for connectivity checks"""
    response = client.get('/api/payment/ping')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert 'confirm' in data['endpoint']


def test_learning_daraja_ping(client):
    """Test learning Daraja ping endpoint"""
    response = client.get('/learning/daraja/ping')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'ok'
    assert data['message'] == 'pong'


def test_callback_mock_format(client, app, sample_transaction):
    """Test callback with mock/simplified format (not full Daraja structure)"""
    with app.app_context():
        transaction = Transaction.query.get(sample_transaction)
        
        # Simplified callback format from mock
        callback_data = {
            "checkout_request_id": "MOCK_12345",
            "merchant_request_id": "MOCK_MR_12345",
            "ResultCode": 0,
            "ResultDesc": "Mock success",
            "phone_number": "254712345678",
            "amount": 100,
            "receipt_number": "MOCK_RECEIPT_123"
        }
        
        response = client.post('/api/payment/confirm', json=callback_data)
        assert response.status_code == 200
        
        # Should process successfully
        db.session.refresh(transaction)
        assert transaction.status == TransactionStatus.SUCCESS
        assert transaction.mpesa_receipt == "MOCK_RECEIPT_123"
