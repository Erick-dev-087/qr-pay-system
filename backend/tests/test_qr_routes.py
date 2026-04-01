import routes.qr_routes as qr_routes_module

from extensions import db
from models import QRCode, QR_Type, QRStatus, ScanLog


def test_generate_qr_rejects_non_vendor(client, make_user, auth_header):
    user_id = make_user()

    response = client.post('/api/qr/generate', json={'qr_type': 'STATIC'}, headers=auth_header(user_id, 'user'))

    assert response.status_code == 403


def test_generate_dynamic_qr_requires_amount(client, make_vendor, auth_header):
    vendor_id = make_vendor(shortcode='QRD001', email='qrd@example.com', phone='254700300001')

    response = client.post('/api/qr/generate', json={'qr_type': 'DYNAMIC'}, headers=auth_header(vendor_id, 'vendor'))

    assert response.status_code == 400


def test_generate_static_qr_success(client, app, make_vendor, auth_header, monkeypatch):
    vendor_id = make_vendor(shortcode='QRS001', email='qrs@example.com', phone='254700300002')

    def _fake_generate_static(self, save_to_db=True):
        qr = QRCode(
            vendor_id=vendor_id,
            payload_data='STATIC-PAYLOAD',
            payload_json={},
            qr_type=QR_Type.STATIC,
            status=QRStatus.ACTIVE,
        )
        db.session.add(qr)
        db.session.commit()
        return qr

    monkeypatch.setattr(qr_routes_module.QR_utils, 'generate_merchant_qr', _fake_generate_static)

    response = client.post('/api/qr/generate', json={'qr_type': 'STATIC'}, headers=auth_header(vendor_id, 'vendor'))
    data = response.get_json()

    assert response.status_code == 201
    assert data['qr_code']['type'] == 'static'


def test_scan_qr_success_creates_scan_log(client, app, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300010', email='scan.user@example.com')
    vendor_id = make_vendor(shortcode='QSCAN1', email='scan.vendor@example.com', phone='254700300011')
    payload = 'VALID-PAYLOAD-001'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {'business_shortcode': 'QSCAN1', 'amount': None, 'reference_number': None, 'currency': '404'}),
    )

    response = client.post('/api/qr/scan', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['vendor']['business_shortcode'] == 'QSCAN1'

    with app.app_context():
        assert ScanLog.query.count() == 1


def test_scan_qr_blocks_vendor_scanning_own_qr(client, make_vendor, make_qr, auth_header, monkeypatch):
    vendor_id = make_vendor(shortcode='QSELF1', email='self.scan@example.com', phone='254700300020')
    payload = 'VALID-PAYLOAD-SELF'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {'business_shortcode': 'QSELF1', 'amount': None, 'reference_number': None, 'currency': '404'}),
    )

    response = client.post('/api/qr/scan', json={'payload': payload}, headers=auth_header(vendor_id, 'vendor'))

    assert response.status_code == 403


def test_validate_qr_success(client, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300030', email='validate.user@example.com')
    vendor_id = make_vendor(shortcode='QVAL01', email='validate.vendor@example.com', phone='254700300031')
    payload = 'VALID-PAYLOAD-VAL'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {'business_shortcode': 'QVAL01', 'amount': 120, 'reference_number': 'REF1', 'currency': '404'}),
    )

    response = client.post('/api/qr/validate', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is True
    assert data['vendor']['business_shortcode'] == 'QVAL01'
