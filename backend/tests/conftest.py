import sys
import os
from pathlib import Path
import pytest

# Ensure test environment is configured before app import
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret')

# Ensure the backend package (project root for the tests) is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from extensions import db
from models import User, Vendor, QRCode, QR_Type, QRStatus
from flask_jwt_extended import create_access_token


@pytest.fixture()
def app():
    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_user(app):
    def _make_user(name='Abigael Wairimu', phone='254719890764', email='abigaelwairimu@gmail.com', password='Abi_2014'):
        with app.app_context():
            user = User(name=name, phone_number=phone, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            return user.id

    return _make_user


@pytest.fixture()
def make_vendor(app):
    def _make_vendor(
        name='Test Vendor',
        shortcode='174379',
        shortcode_type='TILL',
        paybill_account_number=None,
        airtel_number=None,
        kcb_account=None,
        equity_account=None,
        coop_account=None,
        absa_account=None,
        ncba_account=None,
        phone='254700000002',
        email='vendor@example.com',
        password='vendorpass',
        active=True,
    ):
        with app.app_context():
            vendor = Vendor(
                name=name,
                business_shortcode=shortcode,
                shortcode_type=shortcode_type,
                paybill_account_number=paybill_account_number,
                airtel_number=airtel_number,
                kcb_account=kcb_account,
                equity_account=equity_account,
                coop_account=coop_account,
                absa_account=absa_account,
                ncba_account=ncba_account,
                merchant_id='MERCH001',
                mcc='5812',
                store_label='Main Branch',
                email=email,
                phone=phone,
                is_active=active,
            )
            vendor.set_password(password)
            db.session.add(vendor)
            db.session.commit()
            return vendor.id

    return _make_vendor


@pytest.fixture()
def make_qr(app):
    def _make_qr(vendor_id, payload='TESTPAYLOAD', qr_type=QR_Type.STATIC, status=QRStatus.ACTIVE, payload_json=None):
        with app.app_context():
            qr = QRCode(
                vendor_id=vendor_id,
                payload_data=payload,
                payload_json=payload_json or {},
                qr_type=qr_type,
                status=status,
            )
            db.session.add(qr)
            db.session.commit()
            return qr.id

    return _make_qr


@pytest.fixture()
def auth_header(app):
    def _auth_header(identity, user_type):
        with app.app_context():
            token = create_access_token(identity=str(identity), additional_claims={'user_type': user_type})
            return {'Authorization': f'Bearer {token}'}

    return _auth_header
