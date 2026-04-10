from datetime import datetime, timezone
from enum import Enum
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    last_logout = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Define named constraints
    __table_args__ = (
        db.UniqueConstraint('phone_number', name='uq_user_phone_number'),
        db.UniqueConstraint('email', name='uq_user_email'),
    )

    transactions = db.relationship("Transaction", back_populates="user")
    payment_sessions = db.relationship("PaymentSession", back_populates="user")
    scan_logs = db.relationship("ScanLog", back_populates="user")

    def __repr__(self):
        return f"<User {self.name}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
  

class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_name = db.Column(db.String(150), nullable=True)  # Optional business/store name
    business_shortcode = db.Column(db.String(20), unique=True, nullable=False) # Till, Pochi or Paybill
    shortcode_type = db.Column(db.String(20), nullable=False, default="TILL")  # TILL or PAYBILL
    paybill_account_number = db.Column(db.String(50), nullable=True)  # Optional account reference for Paybill
    airtel_number = db.Column(db.String(20), nullable=True)  # Optional Airtel Money number for slot 29
    kcb_account = db.Column(db.String(30), nullable=True)  # Optional KCB account for slot 30
    equity_account = db.Column(db.String(30), nullable=True)  # Optional Equity account for slot 31
    coop_account = db.Column(db.String(30), nullable=True)  # Optional Co-op account for slot 32
    absa_account = db.Column(db.String(30), nullable=True)  # Optional ABSA account for slot 33
    ncba_account = db.Column(db.String(30), nullable=True)  # Optional NCBA account for slot 34
    merchant_id = db.Column(db.String(100), nullable = True) #For CBK/PSP routings
    mcc = db.Column(db.String(8),nullable = True) # Merchant Category code
    country_code = db.Column(db.String(2), default = "KE")
    currency_code = db.Column(db.String(3), default = "404") #Shows currecy is KES
    store_label = db.Column(db.String(50), nullable=True) #Store location
    email = db.Column(db.String(120), nullable=False) 
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    psp_id = db.Column(db.String(100), nullable=True) #ID of the PSP
    psp_name = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    last_logout = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


    # Define named constraints
    __table_args__ = (
        db.UniqueConstraint('email', name='uq_vendor_email'),
        db.UniqueConstraint('phone', name='uq_vendor_phone'),
        db.UniqueConstraint('business_shortcode', name='uq_vendor_business_shortcode'),
    )


    transactions = db.relationship("Transaction", back_populates="vendor")
    qr_code = db.relationship("QRCode", back_populates="vendor", uselist=False)

    def __repr__(self):
        return f"<Vendor {self.name}>"
    
    def get_display_name(self):
        """Returns business_name if set, otherwise falls back to name"""
        return self.business_name if self.business_name else self.name
    
    def get_category(self):
        """Returns the category name based on MCC code, or 'Other' if not found"""
        import json
        import os
        
        if not self.mcc:
            return "Other"
        
        # Load MCC mapping from JSON file
        mcc_file = os.path.join(os.path.dirname(__file__), '..', 'utils', 'mcc_categories.json')
        try:
            with open(mcc_file, 'r') as f:
                mcc_map = json.load(f)
            return mcc_map.get(self.mcc, "Other")
        except (FileNotFoundError, json.JSONDecodeError):
            return "Other"

    def get_shortcode_type(self):
        """Return normalized shortcode type."""
        return (self.shortcode_type or "TILL").strip().upper()

    def is_till(self):
        return self.get_shortcode_type() == "TILL"

    def is_paybill(self):
        return self.get_shortcode_type() == "PAYBILL"
        
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class TransactionStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TransactionType(Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"

class OutflowReason(Enum):
    """
    Reasons why money leaves a vendor account.
    Only applicable when TransactionType is OUTGOING.
    """
    REFUND = "refund"              # Vendor refunding customer
    TRANSFER = "transfer"          # Vendor-to-vendor transfer
    PAYOUT = "payout"              # Vendor withdrawing to bank
    SETTLEMENT = "settlement"      # Payment settlement/clearance
    PLATFORM_FEE = "platform_fee"  # Platform service charges
    ADJUSTMENT = "adjustment"      # Manual correction/adjustment

class Transaction(db.Model):
    __tablename__ ="transactions"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default = "404")
    type = db.Column(db.Enum(TransactionType), nullable=False, default=TransactionType.INCOMING)
    status = db.Column(db.Enum(TransactionStatus), nullable=False, default = TransactionStatus.PENDING)
    
    # Outflow reason - only relevant for OUTGOING transactions
    # Nullable because INCOMING transactions don't need it
    outflow_reason = db.Column(db.Enum(OutflowReason), nullable=True)
    
    mpesa_receipt = db.Column(db.String(150), nullable=True, index = True) #Mpesa receipt
    phone = db.Column(db.String(20), nullable=True) #Payer phone
    callback_response = db.Column(db.JSON, nullable =True) # Callback from Daraja
    initated_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc), nullable = False)
    completed_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc), nullable = False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # NULL for vendor outflows
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)  # NULL for user-only transactions
    qrcode_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id"), nullable= True)  # NULL for non-QR transactions

    user = db.relationship("User", back_populates="transactions")
    vendor = db.relationship("Vendor", back_populates="transactions")
    qr_code = db.relationship("QRCode", back_populates="transactions")
    payment_session = db.relationship("PaymentSession", back_populates="transaction")

    def __repr__(self):
        return f"<Transaction {self.id} - {self.type.value} - {self.status.value}>"
    
    @property
    def is_vendor_outflow(self):
        """Check if this is a vendor outgoing transaction"""
        return self.type == TransactionType.OUTGOING and self.outflow_reason is not None

 
class QRStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"

class QR_Type(Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


class QRCode(db.Model):
    __tablename__ = "qr_codes"

    id = db.Column(db.Integer, primary_key=True)
    payload_data = db.Column(db.Text, nullable=False) # Encoded payload (EMVCo string)
    payload_json = db.Column(db.JSON, nullable = True)
    qr_type = db.Column(db.Enum(QR_Type), nullable = False, default = QR_Type.STATIC)
    status = db.Column(db.Enum(QRStatus), nullable=False, default = QRStatus.ACTIVE)
    created_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc))

    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable= False)
    currency_code = db.Column(db.String(3), default = "404")
    reference_number = db.Column(db.String(50), nullable = True)
    last_scanned_at = db.Column(db.DateTime, default = lambda: datetime.now(timezone.utc))

    vendor = db.relationship("Vendor", back_populates="qr_code")
    transactions = db.relationship("Transaction", back_populates="qr_code")
    scan_logs = db.relationship("ScanLog", back_populates="qr_code")
    payment_sessions = db.relationship("PaymentSession", back_populates="qr_code")


    def __repr__(self):
        return f"<QrCode {self.id} - {self.status }>"


class ScanStatus(Enum):
    SCANNED_ONLY = "scanned_only"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"


class ScanLog(db.Model):
    __tablename__ = "scanlogs"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.Enum(ScanStatus), nullable=False, default = ScanStatus.SCANNED_ONLY)
    timestamp = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc))

    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    user = db.relationship("User", back_populates="scan_logs")
    qr_code = db.relationship("QRCode", back_populates="scan_logs")


    def __repr__(self):
        return f"<ScanLog {self.id} - {self.status}>"


class  PaymentStatus(Enum):
    PAYMENT_INITIATED = "initiated"
    PAYMENT_PENDING = "pending"
    PAYMENT_EXPIRED = "expired"


class PaymentSession(db.Model):
    __tablename__ = "payment_sessions"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default = PaymentStatus.PAYMENT_INITIATED)
    started_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc))
    expired_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc))

    qr_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)  # Link to transaction

    user = db.relationship("User", back_populates="payment_sessions")
    qr_code = db.relationship("QRCode", back_populates="payment_sessions")
    transaction = db.relationship("Transaction", back_populates="payment_session", uselist=False)

    def __repr__(self):
        return f"<PaymentSession {self.id} - {self.status}>"