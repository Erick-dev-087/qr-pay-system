"""
Kenya QR Code Generator — CBK KE-QR Code Standard 2023
Generates payloads that exactly mirror Safaricom's own QR structure,
as reverse-engineered from a live Safaricom app payload.

Verified field layout (matches Safaricom byte-for-byte where static data
is the same; dynamic fields like timestamp naturally differ):

  00 → Payload Format Indicator
  01 → Point of Initiation (11=static, 12=dynamic)
  28 → Merchant Account (ke.go.qr GUID + account number)  [primary]
  29 → Merchant Account (ke.go.qr GUID only)              [interop flag]
  52 → Merchant Category Code
  53 → Transaction Currency (404 = KES)
  54 → Amount (optional)
  58 → Country Code (KE)
  59 → Merchant / Recipient Name (max 25 chars, uppercase)
  61 → Postal Code ("00" — Safaricom convention)
  62 → Additional Data (sub[05] = reference label)
  64 → Language Template (EN)
  82 → QR Timestamp (ke.go.qr + DDMMYYYY HHMMSS)
  83 → M-PESA Routing Block (m-pesa.com + transaction type + limits)
  63 → CRC-16/CCITT-FALSE checksum

   
PSP GUID reference (reverse-engineered from live payloads):
  Safaricom  → 'ke.go.qr'  in slot 28
  Equity     → '68'         in slot 29  (abbreviated CBK UID 0000068)
  Airtel     → 'ke.go.qr'  in slot 30
  Other banks → 'ke.go.qr' in slots 31+
 
"""

import qrcode
from datetime import datetime
from models import QRCode, Vendor, QR_Type, QRStatus
from extensions import db


# ── Transaction type codes (field 83 sub[01]) ────────────────────────────────
# These tell the MPESA app which payment flow to open after scanning.
TRX_TYPE = {
    "WA": "01",   # Withdraw at Agent
    "SM": "02",   # Send Money (person-to-person)
    "BG": "03",   # Buy Goods / Till Number
    "PB": "04",   # Pay Bill
    "SB": "05",   # Send to Business (B2B)
}

# MCC defaults per transaction type — override via vendor.mcc if set
DEFAULT_MCC = {
    "BG": "5411",   # Grocery stores / supermarkets (common till default)
    "PB": "4900",   # Utilities (common paybill default)
    "SM": "0000",   # Person-to-person has no merchant category
    "WA": "6011",   # Cash / agent withdrawal
    "SB": "7372",   # Business services
}


# Optional interoperability slots for additional payment rails.
# UID values are kept for reference/traceability; the active GUID in sub-tag 00
# remains ke.go.qr per current KE-QR interoperable payload behavior.
INTEROP_SLOTS = [
    {"slot": "30", "field": "airtel_number",  "provider": "airtel", "uid": "0800002"},
    {"slot": "31", "field": "kcb_account",    "provider": "kcb",    "uid": "0000001"},
    {"slot": "32", "field": "coop_account",   "provider": "coop",   "uid": "0000011"},
    {"slot": "33", "field": "absa_account",   "provider": "absa",   "uid": "0000003"},
    {"slot": "34", "field": "ncba_account",   "provider": "ncba",   "uid": "0000007"},
]


class QR_utils:
    """
    Generates CBK-compliant KE-QR payloads that mirror Safaricom's own
    app output, including the ke.go.qr GUID, timestamp (field 82),
    and M-PESA routing block (field 83).

    Usage:
        utils = QR_utils(vendor)
        image, payload, db_record = utils.generate_till_qr()
        image, payload, db_record = utils.generate_paybill_qr(amount=500)
        image, payload, db_record = utils.generate_transaction_qr(
            trx_type="BG", amount=250.00, reference="INV-001"
        )
    """

    def __init__(self, vendor: Vendor):
        self.vendor = vendor
        self._validate_vendor()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def generate_till_qr(self, save_to_db: bool = True):
        """
        Static QR for a Till Number (Buy Goods).
        Customer scans → amount prompt → enters PIN.
        Use for: storefront stickers, business cards.
        """
        return self._generate("BG", amount=None, reference=None,
                               save_to_db=save_to_db)

    def generate_paybill_qr(self, amount: float | None = None,
                             account_number: str | None = None,
                             save_to_db: bool = True):
        """
        QR for a Pay Bill number.
        account_number maps to field 62 sub[01] (bill/account number).
        """
        return self._generate("PB", amount=amount, reference=account_number,
                               save_to_db=save_to_db)

    def generate_transaction_qr(self, trx_type: str = "BG",
                                 amount: float | None = None,
                                 reference: str | None = None,
                                 save_to_db: bool = True):
        """
        Generate a QR for any supported transaction type with an optional
        fixed amount and reference number embedded.

        trx_type: "BG" | "PB" | "SM" | "WA" | "SB"
        """
        if trx_type not in TRX_TYPE:
            raise ValueError(
                f"Unknown trx_type '{trx_type}'. "
                f"Use one of: {list(TRX_TYPE.keys())}"
            )
        return self._generate(trx_type, amount=amount, reference=reference,
                               save_to_db=save_to_db)

    # ─────────────────────────────────────────────────────────────────────────
    # Static utilities (usable without a vendor instance)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def calculate_crc(payload: str) -> str:
        """
        CRC-16/CCITT-FALSE  (poly=0x1021, init=0xFFFF, no reflection).

        Pass the full payload string up to and INCLUDING '6304'
        (the ID + declared length of field 63), but NOT the 4-char value.

            crc_input = body + "6304"
            crc_value = QR_utils.calculate_crc(crc_input)
        """
        crc = 0xFFFF
        for byte in payload.encode("utf-8"):
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return f"{crc:04X}"

    @staticmethod
    def validate_crc(payload: str) -> bool:
        """
        Return True if the CRC embedded in the payload is correct.
        Payload must end with '6304XXXX'.
        """
        if len(payload) < 8 or payload[-8:-4] != "6304":
            return False
        return payload[-4:].upper() == QR_utils.calculate_crc(payload[:-4])

    @staticmethod
    def parse_payload(payload: str) -> dict:
        """
        Decode a KE-QR payload into a readable dict.
        Handles nested sub-templates for all merchant account blocks.
        """
        if not payload or len(payload) < 20:
            raise ValueError("Payload too short")

        def _tlv(s: str) -> dict:
            out = {}
            i = 0
            while i < len(s) - 3:
                tag = s[i:i+2]
                try:
                    ln = int(s[i+2:i+4])
                except ValueError:
                    break
                out[tag] = s[i+4:i+4+ln]
                i += 4 + ln
            return out

        f = _tlv(payload)

        result = {
            "format_indicator":    f.get("00"),
            "point_of_initiation": f.get("01"),   # "11"=static "12"=dynamic
            "mcc":                 f.get("52"),
            "currency":            f.get("53"),
            "amount":              f.get("54"),
            "country_code":        f.get("58"),
            "merchant_name":       f.get("59"),
            "equity_account":      f.get("60"), 
            "postal_code":         f.get("61"),
            "additional_data":     f.get("62"),
            "language":            f.get("64"),
            "timestamp":           f.get("82"),
            "mpesa_routing":       f.get("83"),
            "crc":                 f.get("63"),
            "crc_valid":           QR_utils.validate_crc(payload),
            "psp_accounts":        {},
        }

        # Decode every merchant account sub-template
        for tid in [f"{n:02d}" for n in range(2, 52)]:
            if tid in f:
                sub = _tlv(f[tid])
                result["psp_accounts"][tid] = {
                    "guid":    sub.get("00"),
                    "account": sub.get("01"),
                }

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _tlv(tag: str, value: str) -> str:
        """Encode one TLV field: TAG + zero-padded length + VALUE."""
        return f"{tag}{len(value):02d}{value}"

    def _validate_vendor(self):
        required = ["name", "business_shortcode", "country_code", "currency_code"]
        for field in required:
            if not getattr(self.vendor, field, None):
                raise ValueError(f"Vendor missing required field: {field}")

    def _timestamp(self) -> str:
        """
        Generate a 15-char timestamp matching Safaricom's format:
            DDMMYYYY HHMMSS  (always exactly 15 chars, zero-padded)

        Example: April 9 2026 at 14:30:00 → '09042026 143000'

        Note: Safaricom's own server uses no zero-padding for single-digit
        days (e.g. '8042026 ...' for day 8), producing the same 15 chars
        only for days 10–31. We use standard zero-padded DDMMYYYY which
        is always exactly 15 chars and equally valid.
        """
        return datetime.now().strftime("%d%m%Y %H%M%S")

    def _build_payload(self, trx_type: str, amount: float | None,
                        reference: str | None) -> str:
        """
        Assemble the full CBK-compliant TLV string, mirroring the
        exact field order and structure from Safaricom's own app.
        """
        t = self._tlv   # shorthand

        account   = self.vendor.business_shortcode
        name      = self.vendor.name[:25].upper()
        mcc       = self.vendor.mcc or DEFAULT_MCC.get(trx_type, "0000")
        f83_type  = TRX_TYPE[trx_type]
        timestamp = self._timestamp()
        equity_account = getattr(self.vendor, "equity_account", None)

        # ── Slot 28: primary merchant account (GUID + account number) ─────────
        slot_28 = t("28", t("00", "ke.go.qr") + t("01", account))

       # Equity's EazzyApp scanner is hardcoded to look for GUID '68' in
        # slot 29. Using 'ke.go.qr' here causes Equity to reject the QR.
        # When no Equity account is configured, keep the ke.go.qr interop
        # flag (original behaviour, harmless to all other scanners).
        if equity_account:
            slot_29 = t("29", t("00", "68") + t("01", str(equity_account)))
        else:
            slot_29 = t("29", t("00", "ke.go.qr"))

        # ── Optional bank/interoperability account slots (30-34) ─────────────
        # These are only emitted when a corresponding vendor account is present.
        extra_slots = ""
        for slot_config in INTEROP_SLOTS:
            account_value = getattr(self.vendor, slot_config["field"], None)
            if account_value:
                extra_slots += t(
                    slot_config["slot"],
                    t("00", "ke.go.qr") + t("01", str(account_value))
                )

        # ── Field 62: Additional data template ───────────────────────────────
        # sub[05] = Reference Label — Safaricom always sets this to "04"
        # For Pay Bill, sub[01] also carries the account/bill number
        if trx_type == "PB" and reference:
            sub_62 = t("01", reference[:25]) + t("05", "04")
        else:
            sub_62 = t("05", "04")

        # ── Field 64: Language template ───────────────────────────────────────
        sub_64 = t("00", "EN")

        # ── Field 82: QR generation timestamp ────────────────────────────────
        # ke.go.qr namespace + DDMMYYYY HHMMSS timestamp
        # Enables QR expiry validation on the receiving app
        sub_82 = t("00", "ke.go.qr") + t("01", timestamp)

        # ── Field 83: M-PESA proprietary routing block ────────────────────────
        # sub[00] = m-pesa.com namespace identifier
        # sub[01] = transaction type (tells MPESA app which flow to open)
        # sub[03] = minimum allowed amount ("00000" = no minimum)
        # sub[04] = maximum allowed amount ("00000" = no maximum)
        sub_83 = (
            t("00", "m-pesa.com")
            + t("01", f83_type)
            + t("03", "00000")
            + t("04", "00000")
        )

        # ── Assemble in Safaricom's exact field order ─────────────────────────
        payload = (
            t("00", "01")                        # Payload format indicator
            + t("01", "12" if amount else "11")  # 11=static, 12=dynamic
            + slot_28                            # Primary merchant account
            + slot_29                            # Interop flag
            + extra_slots                        # Optional Airtel/bank slots
            + t("52", mcc)                       # Merchant category code
            + t("53", self.vendor.currency_code) # Currency (404 = KES)
        )

        if amount is not None:
            payload += t("54", f"{float(amount):.2f}")  # Amount (2 decimal places)

        payload += (
            t("58", self.vendor.country_code)    # Country code (KE)
            + t("59", name))                     # Merchant name (uppercase)
        
        if equity_account:
            payload += t("60", str(equity_account))

        payload +=(                
            t("61", "00")                      # Postal code (Safaricom default)
            + t("62", sub_62)                    # Additional data / reference
            + t("64", sub_64)                    # Language template
            + t("82", sub_82)                    # Timestamp
            + t("83", sub_83)                    # M-PESA routing
        )

        # ── CRC (always the very last field) ─────────────────────────────────
        # Computed over everything including "6304" (ID + length of field 63)
        # but NOT including the 4-char CRC value itself.
        crc = self.calculate_crc(payload + "6304")
        return payload + "6304" + crc

    def _generate(self, trx_type: str, amount: float | None,
                   reference: str | None, save_to_db: bool):
        """Core: build payload, render image, optionally save to DB."""
        payload   = self._build_payload(trx_type, amount, reference)
        image     = self._render_image(payload)
        qr_type   = QR_Type.DYNAMIC if amount is not None else QR_Type.STATIC
        qr_record = None

        if save_to_db:
            payload_json = {
                "vendor_id": self.vendor.id,
                "vendor_name": self.vendor.name,
                "business_shortcode": self.vendor.business_shortcode,
                "shortcode_type": getattr(self.vendor, "shortcode_type", "TILL"),
                "paybill_account_number": getattr(self.vendor, "paybill_account_number", None),
                "airtel_number": getattr(self.vendor, "airtel_number", None),
                "kcb_account": getattr(self.vendor, "kcb_account", None),
                "equity_account": getattr(self.vendor, "equity_account", None),
                "coop_account": getattr(self.vendor, "coop_account", None),
                "absa_account": getattr(self.vendor, "absa_account", None),
                "ncba_account": getattr(self.vendor, "ncba_account", None),
                "currency": self.vendor.currency_code,
                "trx_type": trx_type,
                "timestamp": datetime.now().isoformat(),
            }
            if amount is not None:
                payload_json["amount"] = float(amount)
            if reference:
                payload_json["reference"] = reference

            qr_record = QRCode(
                vendor_id=self.vendor.id,
                payload_data=payload,
                payload_json=payload_json,
                qr_type=qr_type,
                status=QRStatus.ACTIVE,
                currency_code=self.vendor.currency_code,
                reference_number=reference,
            )
            db.session.add(qr_record)
            db.session.commit()

        return image, payload, qr_record

    def _render_image(self, payload: str):
        """Render payload string to a PIL image."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
    
    # ============= Database Retrieval Methods =============
    
    @staticmethod
    def get_qr_by_id(qr_id):
        """
        Retrieve a QR code by its database ID
        
        Args:
            qr_id: The database ID of the QR code
            
        Returns:
            QRCode object or None if not found
        """
        return QRCode.query.get(qr_id)
    
    @staticmethod
    def get_qr_by_reference(reference_number):
        """
        Retrieve a QR code by its reference number
        
        Args:
            reference_number: The transaction reference number
            
        Returns:
            QRCode object or None if not found
        """
        return QRCode.query.filter_by(reference_number=reference_number).first()
    
    def get_all_vendor_qrs(self, status=None, qr_type=None):
        """
        Get all QR codes for the current vendor
        
        Args:
            status: Optional QRStatus filter (ACTIVE, INACTIVE, EXPIRED)
            qr_type: Optional QR_Type filter (STATIC, DYNAMIC)
            
        Returns:
            List of QRCode objects
        """
        query = QRCode.query.filter_by(vendor_id=self.vendor.id)
        
        if status:
            query = query.filter_by(status=status)
        if qr_type:
            query = query.filter_by(qr_type=qr_type)
        
        return query.all()
    
    def get_active_merchant_qr(self):
        """
        Get the active merchant QR (static, no amount) for this vendor
        Typically, each vendor has one permanent merchant QR
        
        Returns:
            QRCode object or None if not found
        """
        return QRCode.query.filter_by(
            vendor_id=self.vendor.id,
            qr_type=QR_Type.STATIC,
            status=QRStatus.ACTIVE
        ).filter(QRCode.reference_number.is_(None)).first()
    
    @staticmethod
    def deactivate_qr(qr_id):
        """
        Deactivate a QR code (mark as inactive)
        
        Args:
            qr_id: The database ID of the QR code to deactivate
            
        Returns:
            Updated QRCode object or None if not found
        """
        qr_code = QRCode.query.get(qr_id)
        if qr_code:
            qr_code.status = QRStatus.INACTIVE
            db.session.commit()
        return qr_code
    
    @staticmethod
    def expire_qr(qr_id):
        """
        Expire a QR code (mark as expired)
        
        Args:
            qr_id: The database ID of the QR code to expire
            
        Returns:
            Updated QRCode object or None if not found
        """
        qr_code = QRCode.query.get(qr_id)
        if qr_code:
            qr_code.status = QRStatus.EXPIRED
            db.session.commit()
        return qr_code