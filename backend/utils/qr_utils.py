import qrcode
from qrcode.constants import ERROR_CORRECT_M
from datetime import datetime, timezone
from models import QRCode, Vendor,QR_Type, QRStatus
from extensions import db

class QR_utils():
    """
    Kenya QR code Generator - CBK Compliant
    """
    def __init__(self, vendor :Vendor):
        self.vendor = vendor
        self.validate_vendor_data()

    # KE-QR sub-template GUID for Safaricom M-Pesa (default PSP block)
    DEFAULT_PSP_GUID = "com.safaricom.mpesa"
    VALID_SHORTCODE_TYPES = {"TILL", "PAYBILL"}

    @staticmethod
    def _tlv(field_id, value):
        """Build a TLV fragment with 2-digit ID + 2-digit length."""
        text_value = str(value)
        return f"{field_id}{len(text_value):02d}{text_value}"

    @staticmethod
    def _parse_tlv(payload):
        """Parse TLV payload into a dict preserving first value per field ID."""
        fields = {}
        i = 0
        while i < len(payload):
            if i + 4 > len(payload):
                raise ValueError("Malformed payload: incomplete TLV header")
            field_id = payload[i:i + 2]
            try:
                field_length = int(payload[i + 2:i + 4])
            except ValueError as exc:
                raise ValueError("Malformed payload: invalid TLV length") from exc
            start = i + 4
            end = start + field_length
            if end > len(payload):
                raise ValueError("Malformed payload: value exceeds payload length")
            fields.setdefault(field_id, payload[start:end])
            i = end
        return fields

    @staticmethod
    def _build_data_enrichment_template(reference_number=None):
        """Build ID 62 sub-template (Data Enrichment Template) if reference is provided."""
        if not reference_number:
            return None
        # 62.01 = bill/reference number in a compact interoperable sub-field.
        sub_template = QR_utils._tlv("01", str(reference_number))
        return sub_template

    @staticmethod
    def _build_merchant_account_template(shortcode, guid=None, shortcode_type="TILL", paybill_account_number=None, extra_fields=None):
        """Build ID 26 merchant account sub-template with core and extensible fields."""
        psp_guid = guid or QR_utils.DEFAULT_PSP_GUID
        normalized_type = (shortcode_type or "TILL").strip().upper()

        fragments = [
            QR_utils._tlv("00", psp_guid),
            QR_utils._tlv("01", shortcode),
            QR_utils._tlv("02", normalized_type),
        ]

        if normalized_type == "PAYBILL" and paybill_account_number:
            fragments.append(QR_utils._tlv("03", str(paybill_account_number)))

        if extra_fields:
            for field_id, field_value in sorted(extra_fields.items()):
                # Preserve space for future platform-specific extensions.
                if field_id in {"00", "01", "02", "03"}:
                    continue
                fragments.append(QR_utils._tlv(str(field_id), field_value))

        sub_template = "".join(fragments)
        return sub_template
    
    @staticmethod
    def calculate_crc(payload):
        """Calculate CRC-16-CCITT checksum (static method - no vendor needed)"""
        crc = 0xFFFF
        
        for byte in payload.encode('utf-8'):
            crc ^= byte << 8
            
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        
        return f"{crc:04X}"
    
    @staticmethod
    def parse_payload(payload):
        """Parse CBK-compliant QR payload (static method - no vendor needed)"""
        if not payload or len(payload) < 20:
            raise ValueError("Invalid payload: too short")

        fields = QR_utils._parse_tlv(payload)

        merchant_account = fields.get('26') or fields.get('02')
        business_shortcode = None
        shortcode_type = None
        paybill_account_number = None
        psp_guid = None
        if merchant_account:
            try:
                sub_fields = QR_utils._parse_tlv(merchant_account)
                psp_guid = sub_fields.get('00')
                business_shortcode = sub_fields.get('01')
                shortcode_type = sub_fields.get('02')
                paybill_account_number = sub_fields.get('03')
            except ValueError:
                # Backward compatibility with older payloads where 02 stored raw shortcode.
                business_shortcode = merchant_account

        if not shortcode_type:
            shortcode_type = 'TILL'

        data_enrichment = fields.get('62')
        reference_number = None
        if data_enrichment:
            try:
                reference_number = QR_utils._parse_tlv(data_enrichment).get('01')
            except ValueError:
                reference_number = data_enrichment

        return {
            'format_indicator': fields.get('00'),
            'psp_guid': psp_guid,
            'business_shortcode': business_shortcode,
            'shortcode_type': shortcode_type,
            'paybill_account_number': paybill_account_number,
            'mcc': fields.get('52'),
            'currency': fields.get('53'),
            'amount': fields.get('54'),
            'country_code': fields.get('58'),
            'merchant_name': fields.get('59'),
            'merchant_city': fields.get('60'),
            'postal_code': fields.get('61'),
            'reference_number': reference_number,
            'crc_field': fields.get('63')
        }
    
    @staticmethod
    def validate_crc(payload):
        """Verify CRC checksum in payload (static method)"""
        if len(payload) < 8:
            return False

        provided_crc = payload[-4:]

        # Calculate expected CRC over payload up to and including "6304".
        crc_input = payload[:-4]
        expected_crc = QR_utils.calculate_crc(crc_input)
        
        return provided_crc.upper() == expected_crc.upper()

    def validate_vendor_data(self):
        """Ensure vendor has all required fields for CBK compliance"""
        required_fields = ['name','business_shortcode','country_code','currency_code']

        for field in required_fields:
            if not getattr(self.vendor, field):
                raise ValueError(f"Vendor missing required field: {field}")

        vendor_shortcode_type = (getattr(self.vendor, 'shortcode_type', 'TILL') or 'TILL').strip().upper()
        if vendor_shortcode_type not in self.VALID_SHORTCODE_TYPES:
            raise ValueError("Vendor shortcode_type must be either TILL or PAYBILL")

    def _build_cbk_payload(self, amount=None, reference_number = None):
        """Bulding the string that goes into the QR code"""
        shortcode_type = (getattr(self.vendor, 'shortcode_type', 'TILL') or 'TILL').strip().upper()
        merchant_account_template = self._build_merchant_account_template(
            shortcode=self.vendor.business_shortcode,
            guid=self.DEFAULT_PSP_GUID,
            shortcode_type=shortcode_type,
            paybill_account_number=getattr(self.vendor, 'paybill_account_number', None),
        )

        # Field 60 is merchant city; use vendor store_label as fallback for legacy model.
        merchant_city = (self.vendor.store_label or "Nairobi").strip()[:15] or "Nairobi"
        # CBK notes Kenya postal code default can be "00".
        postal_code = "00"

        fields = {
            "00": "01",                              # Payload format indicator
            "01": "12" if amount else "11",          # Dynamic if amount present, else static
            "26": merchant_account_template,           # Merchant Account Information Template
            "52": str(self.vendor.mcc or "0000"),     # Merchant category code
            "53": str(self.vendor.currency_code),      # Transaction currency
            "58": str(self.vendor.country_code),       # Country code (KE)
            "59": str(self.vendor.name)[:25],          # Merchant name
            "60": merchant_city,                       # Merchant city
            "61": postal_code,                         # Postal code/default
        }

        if amount:
            fields["54"] = f"{float(amount):.2f}"

        data_enrichment = self._build_data_enrichment_template(reference_number)
        if data_enrichment:
            fields["62"] = data_enrichment

        payload = "".join(
            self._tlv(field_id, fields[field_id])
            for field_id in sorted(fields.keys())
        )

        payload_for_crc = payload + "6304"
        crc = self._calculate_crc(payload_for_crc)

        final_payload = payload_for_crc + crc

        return final_payload
        

    def _calculate_crc(self, payload):
        """Instance wrapper for static CRC calculation"""
        return QR_utils.calculate_crc(payload)
    
    
    def parse_cbk_payload(self, payload):
        """Extract fields from CBK-compliant payload"""
        fields = self.parse_payload(payload)

        return {
            'business_shortcode' : fields.get('business_shortcode'),
            'shortcode_type': fields.get('shortcode_type'),
            'paybill_account_number': fields.get('paybill_account_number'),
            'amount': fields.get('amount'),
            'reference_number':fields.get('reference_number'),
            'currency': fields.get('currency'),
            'merchant_name': fields.get('merchant_name')

        }


    def _create_qr_image(self, payload):
        qr = qrcode.QRCode(
            version=1,
            error_correction=ERROR_CORRECT_M
        )
        qr.add_data(payload)
        qr.make(fit=True)
        return qr.make_image()
    

    def generate_merchant_qr(self,save_to_db = True):
        """
        Generate a merchant's permanent QR code(no amount)
        Customer scans and enters amount
        use: Print on storefront, business cards, etc.
        """
        payload = self._build_cbk_payload()
        image =  self._create_qr_image(payload)  

        qr_record = None
        if save_to_db:
            qr_record= self.save_to_database(
                payload=payload,
                qr_type=QR_Type.STATIC,
                amount=None,
                reference=None,
                
            )

        return  image, payload, qr_record
        
    
    def generate_fixed_amount_qr(self,amount,save_to_db=True):
        """
        Generate QR with fixes amount(static)
        Customer scans and just confirms
        Use: Fixed-price items, parking fees, entry tickets"""

        payload = self._build_cbk_payload(amount)
        image =  self._create_qr_image(payload)

        qr_record = None
        if save_to_db:
            qr_record = self.save_to_database(
                payload=payload,
                qr_type=QR_Type.STATIC,
                amount=amount,
                reference=None
            )

        return image, payload, qr_record
    
    def generate_transaction_qr(self, amount, reference_number=None,save_to_db=True):
        """
        Generate QR for specific transaction
        Includes amount and unique reference
        """
        payload = self._build_cbk_payload(amount, reference_number)
        image =  self._create_qr_image(payload)

        qr_record = None
        if save_to_db:
            qr_record = self.save_to_database(
                payload=payload,
                qr_type=QR_Type.DYNAMIC,
                amount=amount,
                reference=reference_number,
                 )
        
        return image, payload, qr_record
        
    def save_to_database(self, payload, qr_type,amount = None, reference = None):
        """
        Save QR code payload to database
        """
        payload_json = {
            "vendor_id" : self.vendor.id,
            "vendor_name": self.vendor.name,
            "business_shortcode": self.vendor.business_shortcode,
            "shortcode_type": getattr(self.vendor, 'shortcode_type', 'TILL'),
            "paybill_account_number": getattr(self.vendor, 'paybill_account_number', None),
            "currency": self.vendor.currency_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if amount:
            payload_json["amount"] = amount
        if reference:
            payload_json["reference"] = reference

        qr_code = QRCode(
            payload_data=payload,
            payload_json=payload_json,
            qr_type=qr_type,
            status=QRStatus.ACTIVE,
            vendor_id=self.vendor.id,
            currency_code = self.vendor.currency_code,
            reference_number = reference

        )

        db.session.add(qr_code)
        db.session.commit()

        return qr_code
    
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