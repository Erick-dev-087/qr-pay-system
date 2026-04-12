from models import Vendor
from utils.qr_utils import QR_utils


def _build_vendor(app, *, shortcode, shortcode_type, paybill_account_number=None):
    with app.app_context():
        vendor = Vendor(
            name=f"Vendor {shortcode}",
            business_shortcode=shortcode,
            shortcode_type=shortcode_type,
            paybill_account_number=paybill_account_number,
            merchant_id=f"MERCH-{shortcode}",
            mcc='5812',
            country_code='KE',
            currency_code='404',
            store_label='Main',
            email=f"{shortcode.lower()}@example.com",
            phone=f"254700{shortcode[-6:]}",
        )
        vendor.set_password('password123')
        return vendor


def test_till_qr_payload_has_shortcode_type(app):
    vendor = _build_vendor(app, shortcode='123456', shortcode_type='TILL')

    qr = QR_utils(vendor)
    _, payload, _ = qr.generate_transaction_qr(trx_type='BG', amount=100, save_to_db=False)
    parsed = QR_utils.parse_payload(payload)
    psp_accounts = parsed.get('psp_accounts') or {}

    assert psp_accounts.get('28', {}).get('account') == '123456'
    assert parsed['amount'] == '100.00'
    assert QR_utils.validate_crc(payload) is True


def test_paybill_qr_payload_carries_account_number(app):
    vendor = _build_vendor(
        app,
        shortcode='600000',
        shortcode_type='PAYBILL',
        paybill_account_number='INV-0001',
    )

    qr = QR_utils(vendor)
    _, payload, _ = qr.generate_paybill_qr(amount=250, account_number='INV-0001', save_to_db=False)
    parsed = QR_utils.parse_payload(payload)
    psp_accounts = parsed.get('psp_accounts') or {}
    additional_data = parsed.get('additional_data', '')

    assert psp_accounts.get('28', {}).get('account') == '600000'
    assert parsed['amount'] == '250.00'
    assert '0108INV-0001' in additional_data
    assert QR_utils.validate_crc(payload) is True


def test_universal_production_qr_models_single_payload_strategy(app):
    vendor = _build_vendor(
        app,
        shortcode='9188963',
        shortcode_type='TILL',
    )
    vendor.airtel_number = '0733123456'
    vendor.kcb_account = 'KCB-9188963'
    vendor.equity_account = 'EQ-9188963'

    qr = QR_utils(vendor)
    _, payload, _ = qr.generate_production_qr(save_to_db=False)
    parsed = QR_utils.parse_payload(payload)
    psp_accounts = parsed.get('psp_accounts') or {}

    assert psp_accounts.get('28', {}).get('account') == '9188963'
    assert psp_accounts.get('29', {}).get('guid') == 'ke.go.qr'
    assert psp_accounts.get('30', {}).get('account') == '0733123456'
    assert psp_accounts.get('31', {}).get('account') == 'KCB-9188963'
    assert psp_accounts.get('35', {}).get('account') == 'EQ-9188963'
    assert parsed.get('merchant_city') == 'Main'
    assert QR_utils.validate_crc(payload) is True
