import json
import os
from urllib import error as urlerror
from urllib import request as urlrequest


def _normalize_msisdn(raw_phone):
    digits = ''.join(ch for ch in str(raw_phone or '') if ch.isdigit())
    if len(digits) == 10 and digits.startswith('0'):
        return f"254{digits[1:]}"
    if len(digits) == 12 and digits.startswith('254'):
        return digits
    return None


def _is_probable_kenyan_mobile(msisdn):
    if not msisdn:
        return False
    return msisdn.startswith('2547') or msisdn.startswith('2541')


def build_external_merchant_pitch_message(amount, download_url):
    safe_amount = amount if amount is not None else 'an amount'
    app_name = os.getenv('APP_BRAND_NAME', 'QR Pay')
    if download_url:
        return (
            f"You have received KES {safe_amount} via {app_name}. "
            f"Track and manage payments by joining us: {download_url}"
        )
    return (
        f"You have received KES {safe_amount} via {app_name}. "
        f"Download the app to track and manage payments."
    )


def send_sms(phone, message):
    sms_url = os.getenv('SMS_WEBHOOK_URL', '').strip()
    if not sms_url:
        return False, 'SMS webhook is not configured'

    msisdn = _normalize_msisdn(phone)
    if not _is_probable_kenyan_mobile(msisdn):
        return False, 'No valid mobile phone for external merchant'

    payload = {
        'to': msisdn,
        'message': message,
        'source': os.getenv('APP_BRAND_NAME', 'QR Pay'),
    }

    headers = {'Content-Type': 'application/json'}
    sms_api_key = os.getenv('SMS_API_KEY', '').strip()
    if sms_api_key:
        headers['Authorization'] = f'Bearer {sms_api_key}'

    timeout = float(os.getenv('SMS_WEBHOOK_TIMEOUT_SECONDS', '4'))
    req = urlrequest.Request(
        sms_url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )

    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            status_ok = 200 <= getattr(response, 'status', 500) < 300
            if status_ok:
                return True, 'SMS sent'
            return False, f'SMS provider returned status {getattr(response, "status", "unknown")}'
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError) as exc:
        return False, f'SMS send failed: {exc}'
