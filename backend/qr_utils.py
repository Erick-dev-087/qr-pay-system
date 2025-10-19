import qrcode
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

    def validate_vendor_data(self):
        """Ensure vendor has all required fields for CBK compliance"""
        required_fields = ['name','business_shortcode','country_code','currency_code']

        for field in required_fields:
            if not getattr(self.vendor, field):
                raise ValueError(f"Vendor missing required field: {field}")

    def _build_cbk_payload(self, amount=None, reference_number = None):
        """Bulding the string that goes into the QR code"""
        fields = {
            "00": "01",                             # Payload format indicator
            "01": "12" if amount else "11",         #
            "02": self.vendor.business_shortcode,   # Merchant account(Till/Paybil/Pochi)
            "52": self.vendor.mcc or "0000",        # Merchant category code
            "53": self.vendor.currency_code,        # Transaction currency
            "58": self.vendor.country_code,         # Country code(KE)
            "59": self.vendor.name,                 # Merchant name
            "60": self.vendor.store_label or "",    # Merchant city
            "61": "00",                             # Postal code(Kenya Default)
            
        }

        if amount:
            fields["54"] = str(amount)

        if reference_number:
            fields["62"] = str(reference_number)

        payload = ""
        for field_id, value in fields.items():
            length = f"{len(value):02d}"
            payload += field_id + length + value

        payload_for_crc = payload + "6304"
        crc = self._calculate_crc(payload_for_crc + "0000")

        final_payload = payload + "63" + "04" + crc

        return final_payload
        

    def _calculate_crc(self, payload):
        """Calculating CRC-16-CCITT checksum for CBK compliance"""

        def crc16_ccitt(data):
            crc = 0xFFF

            for byte in data.encode('utf-8'):
                crc ^= byte << 8

                for _ in range(8):
                    if crc & 0x8000:
                        crc = (crc << 1) ^ 0x1021
                    else:
                        crc <<=1
                    crc &=0xFFF

            return f"{crc:04x}"
            
        return crc16_ccitt(payload)


    def _create_qr_image(self, payload):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M
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