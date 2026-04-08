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
    payload = qr._build_cbk_payload(amount=100)
    parsed = QR_utils.parse_payload(payload)

    assert parsed['business_shortcode'] == '123456'
    assert parsed['shortcode_type'] == 'TILL'
    assert parsed['paybill_account_number'] is None


def test_paybill_qr_payload_carries_account_number(app):
    vendor = _build_vendor(
        app,
        shortcode='600000',
        shortcode_type='PAYBILL',
        paybill_account_number='INV-0001',
    )

    qr = QR_utils(vendor)
    payload = qr._build_cbk_payload(amount=250, reference_number='ORDER-1')
    parsed = QR_utils.parse_payload(payload)

    assert parsed['business_shortcode'] == '600000'
    assert parsed['shortcode_type'] == 'PAYBILL'
    assert parsed['paybill_account_number'] == 'INV-0001'
    assert parsed['reference_number'] == 'ORDER-1'
    assert QR_utils.validate_crc(payload) is True
