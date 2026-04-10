from models import Vendor
from utils.qr_utils import QR_utils


def _build_vendor(shortcode: str, *, name: str = 'Test Vendor', mcc: str = '5812'):
    vendor = Vendor(
        name=name,
        business_shortcode=shortcode,
        shortcode_type='TILL',
        merchant_id=f'MERCH-{shortcode}',
        mcc=mcc,
        country_code='KE',
        currency_code='404',
        store_label='Thika',
        email=f'{shortcode.lower()}@example.com',
        phone=f'254700{shortcode[-6:]}',
    )
    vendor.set_password('password123')
    return vendor


def test_generate_till_qr_matches_current_api():
    vendor = _build_vendor('9188963', name='James Kimani')

    qr = QR_utils(vendor)
    _image, payload, _record = qr.generate_till_qr(save_to_db=False)
    parsed = QR_utils.parse_payload(payload)

    assert parsed['point_of_initiation'] == '11'
    assert parsed['merchant_name'] == 'JAMES KIMANI'
    assert parsed['psp_accounts']['28']['account'] == '9188963'
    assert QR_utils.validate_crc(payload) is True


def test_generate_paybill_qr_embeds_amount_and_account_number():
    vendor = _build_vendor('600000', name='Paybill Vendor', mcc='4900')

    qr = QR_utils(vendor)
    _image, payload, _record = qr.generate_paybill_qr(
        amount=250,
        account_number='INV-0001',
        save_to_db=False,
    )
    parsed = QR_utils.parse_payload(payload)

    assert parsed['point_of_initiation'] == '12'
    assert parsed['amount'] == '250.00'
    assert parsed['psp_accounts']['28']['account'] == '600000'
    assert '0108INV-0001' in (parsed.get('additional_data') or '')
    assert QR_utils.validate_crc(payload) is True


def test_generate_transaction_qr_rejects_unknown_trx_type():
    vendor = _build_vendor('174379')
    qr = QR_utils(vendor)

    try:
        qr.generate_transaction_qr(trx_type='XX', amount=100, save_to_db=False)
        assert False, 'Expected ValueError for unknown transaction type'
    except ValueError as exc:
        assert 'Unknown trx_type' in str(exc)


def test_interoperable_slots_include_airtel_and_equity_when_configured():
    vendor = _build_vendor('9188963', name='James Kimani')
    vendor.airtel_number = '0733123456'
    vendor.equity_account = 'EQ-ACC-001'

    qr = QR_utils(vendor)
    _image, payload, _record = qr.generate_till_qr(save_to_db=False)
    parsed = QR_utils.parse_payload(payload)
    psp = parsed.get('psp_accounts') or {}

    assert psp.get('28', {}).get('account') == '9188963'
    assert psp.get('29', {}).get('account') == '0733123456'
    assert psp.get('31', {}).get('account') == 'EQ-ACC-001'
    assert QR_utils.validate_crc(payload) is True
