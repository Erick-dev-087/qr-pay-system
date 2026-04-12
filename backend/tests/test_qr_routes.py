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

    def _fake_generate_static(self, amount=None, reference=None, save_to_db=True):
        qr = QRCode(
            vendor_id=vendor_id,
            payload_data='STATIC-PAYLOAD',
            payload_json={},
            qr_type=QR_Type.STATIC,
            status=QRStatus.ACTIVE,
        )
        db.session.add(qr)
        db.session.commit()
        return None, 'STATIC-PAYLOAD', qr

    monkeypatch.setattr(qr_routes_module.QR_utils, 'generate_production_qr', _fake_generate_static)

    response = client.post('/api/qr/generate', json={'qr_type': 'STATIC'}, headers=auth_header(vendor_id, 'vendor'))
    data = response.get_json()

    assert response.status_code == 201
    assert data['qr_code']['type'] == 'static'
    assert data['qr_code']['profile'] == 'universal'


def test_generate_dynamic_qr_supports_legacy_adaptive_profile(client, app, make_vendor, auth_header, monkeypatch):
    vendor_id = make_vendor(shortcode='QRL001', email='qrl@example.com', phone='254700300003')

    def _fake_generate_dynamic(self, trx_type='BG', amount=None, reference=None, save_to_db=True):
        qr = QRCode(
            vendor_id=vendor_id,
            payload_data='LEGACY-DYNAMIC-PAYLOAD',
            payload_json={},
            qr_type=QR_Type.DYNAMIC,
            status=QRStatus.ACTIVE,
        )
        db.session.add(qr)
        db.session.commit()
        return None, 'LEGACY-DYNAMIC-PAYLOAD', qr

    monkeypatch.setattr(qr_routes_module.QR_utils, 'generate_transaction_qr', _fake_generate_dynamic)

    response = client.post(
        '/api/qr/generate',
        json={'qr_type': 'DYNAMIC', 'qr_profile': 'LEGACY_ADAPTIVE', 'amount': 100},
        headers=auth_header(vendor_id, 'vendor')
    )
    data = response.get_json()

    assert response.status_code == 201
    assert data['qr_code']['type'] == 'dynamic'
    assert data['qr_code']['profile'] == 'legacy_adaptive'


def test_scan_qr_success_creates_scan_log(client, app, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300010', email='scan.user@example.com')
    vendor_id = make_vendor(shortcode='QSCAN1', email='scan.vendor@example.com', phone='254700300011')
    payload = 'VALID-PAYLOAD-001'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'28': {'account': 'QSCAN1'}},
            'amount': None,
            'additional_data': None,
            'currency': '404',
        }),
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
        staticmethod(lambda _payload: {
            'psp_accounts': {'28': {'account': 'QSELF1'}},
            'amount': None,
            'additional_data': None,
            'currency': '404',
        }),
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
        staticmethod(lambda _payload: {
            'psp_accounts': {'28': {'account': 'QVAL01'}},
            'amount': '120.00',
            'additional_data': '0104REF1',
            'currency': '404',
        }),
    )

    response = client.post('/api/qr/validate', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is True
    assert data['vendor']['business_shortcode'] == 'QVAL01'


def test_scan_qr_resolves_shortcode_from_slot29(client, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300040', email='slot29.user@example.com')
    vendor_id = make_vendor(shortcode='QEQ29', email='slot29.vendor@example.com', phone='254700300041')
    payload = 'VALID-PAYLOAD-SLOT29'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'29': {'account': 'QEQ29'}},
            'amount': None,
            'additional_data': None,
            'currency': '404',
        }),
    )

    response = client.post('/api/qr/scan', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    assert response.status_code == 200


def test_validate_qr_resolves_shortcode_from_slot31(client, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300050', email='slot31.user@example.com')
    vendor_id = make_vendor(shortcode='QBK31', email='slot31.vendor@example.com', phone='254700300051')
    payload = 'VALID-PAYLOAD-SLOT31'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'31': {'account': 'QBK31'}},
            'amount': '90.00',
            'additional_data': None,
            'currency': '404',
        }),
    )

    response = client.post('/api/qr/validate', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    assert response.status_code == 200


def test_scan_qr_matches_vendor_by_alternate_account_field(client, make_user, make_vendor, make_qr, auth_header, monkeypatch):
    user_id = make_user(phone='254700300060', email='altacct.user@example.com')
    vendor_id = make_vendor(
        shortcode='QMAIN60',
        airtel_number='0733000060',
        email='altacct.vendor@example.com',
        phone='254700300061',
    )
    payload = 'VALID-PAYLOAD-ALT-ACCOUNT'
    make_qr(vendor_id, payload=payload)

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'30': {'account': '0733000060'}},
            'amount': None,
            'reference': None,
            'additional_data': None,
            'additional_data_fields': {},
            'currency': '404',
            'crc_valid': True,
            'merchant_name': 'Alt Vendor',
        }),
    )

    response = client.post('/api/qr/scan', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['vendor']['business_shortcode'] == 'QMAIN60'


def test_validate_external_qr_requires_user_confirmation(client, make_user, auth_header, monkeypatch):
    user_id = make_user(phone='254700300070', email='external.user@example.com')
    payload = 'VALID-PAYLOAD-EXTERNAL-CONFIRM'

    monkeypatch.setenv('ALLOW_EXTERNAL_QR', 'true')
    monkeypatch.setenv('EXTERNAL_QR_REQUIRE_USER_CONFIRMATION', 'true')
    monkeypatch.setenv('AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM', 'true')

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'31': {'account': 'EXT-CONFIRM-700'}},
            'amount': '140.00',
            'reference': 'INV-EXT-700',
            'additional_data': '0111INV-EXT-700050204',
            'additional_data_fields': {'01': 'INV-EXT-700', '05': '04'},
            'currency': '404',
            'crc_valid': True,
            'merchant_name': 'External Verified Merchant',
            'merchant_city': 'Nairobi',
            'mcc': '4900',
            'point_of_initiation': '12',
        }),
    )

    response = client.post('/api/qr/validate', json={'payload': payload}, headers=auth_header(user_id, 'user'))
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is True
    assert data['requires_confirmation'] is True
    assert data['can_initiate_payment'] is False
    assert data['external_merchant']['merchant_account'] == 'EXT-CONFIRM-700'


def test_validate_external_qr_can_auto_onboard_after_confirmation(client, make_user, auth_header, monkeypatch):
    user_id = make_user(phone='254700300071', email='external.confirm.user@example.com')
    payload = 'VALID-PAYLOAD-EXTERNAL-ONBOARD'

    monkeypatch.setenv('ALLOW_EXTERNAL_QR', 'true')
    monkeypatch.setenv('EXTERNAL_QR_REQUIRE_USER_CONFIRMATION', 'true')
    monkeypatch.setenv('AUTO_ONBOARD_EXTERNAL_QR_ON_CONFIRM', 'true')

    monkeypatch.setattr(qr_routes_module.QR_utils, 'validate_crc', staticmethod(lambda _payload: True))
    monkeypatch.setattr(
        qr_routes_module.QR_utils,
        'parse_payload',
        staticmethod(lambda _payload: {
            'psp_accounts': {'31': {'account': 'EXT-ONBOARD-701'}},
            'amount': '90.00',
            'reference': 'INV-EXT-701',
            'additional_data': '0111INV-EXT-701050204',
            'additional_data_fields': {'01': 'INV-EXT-701', '05': '04'},
            'currency': '404',
            'crc_valid': True,
            'merchant_name': 'External Onboard Merchant',
            'merchant_city': 'Nairobi',
            'mcc': '4900',
            'point_of_initiation': '12',
        }),
    )

    response = client.post(
        '/api/qr/validate',
        json={'payload': payload, 'confirm_external_payment': True},
        headers=auth_header(user_id, 'user')
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data['valid'] is True
    assert data['can_initiate_payment'] is True
    assert data['vendor']['business_shortcode'] == 'EXT-ONBOARD-701'
