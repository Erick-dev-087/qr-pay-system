from datetime import datetime, timezone
from enum import Enum
from extensions import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), unique = True, nullable = False)
   

    transactions = db.relationship("Transaction", back_populates="user")
    payment_sessions = db.relationship("PaymentSession", back_populates="user")
    scan_logs = db.relationship("ScanLog", back_populates="user")

    def __repr__(self):
        return f"<User {self.name}>"

  

class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_shortcode = db.Column(db.String(20), unique=True, nullable=False) # Till, Pochi or Paybill
    merchant_id = db.Column(db.String(100), nullable = True) #For CBK/PSP routings
    mcc = db.Column(db.String(8),nullable = True) # Merchant Category code
    country_code = db.Column(db.String(2), default = "KE")
    currency_code = db.Column(db.String(3), default = "404") #Shows currecy is KES
    store_label = db.Column(db.String(50), nullable=True) #Store location
    email = db.Column(db.String(120), nullable=True) 
    phone = db.Column(db.String(20), nullable=True)
    psp_id = db.Column(db.String(100), nullable=True) #ID of the PSP
    psp_name = db.Column(db.String(150), nullable= True)
    created_at = db.Column(db.DateTime, default= lambda: datetime.now(timezone.utc))


    transactions = db.relationship("Transaction", back_populates="vendor")
    qr_code = db.relationship("QRCode", back_populates="vendor", uselist=False)

    def __repr__(self):
        return f"<Vendor {self.name}>"


class TransactionStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Transaction(db.Model):
    __tablename__ ="transactions"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), default = "404")
    status = db.Column(db.Enum(TransactionStatus), nullable=False, default = TransactionStatus.PENDING)
    mpesa_receipt = db.Column(db.String(150), nullable=True, index = True) #Mpesa receipt
    phone = db.Column(db.String(20), nullable=True) #Payer phone
    callback_response = db.Column(db.JSON, nullable =True) # Callback from Daraja
    initated_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc), nullable = False)
    completed_at = db.Column(db.DateTime, default = lambda : datetime.now(timezone.utc), nullable = False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False)
    qrcode_id = db.Column(db.Integer, db.ForeignKey("qr_codes.id"), nullable= False)

    user = db.relationship("User", back_populates="transactions")
    vendor = db.relationship("Vendor", back_populates="transactions")
    qr_code = db.relationship("QRCode", back_populates="transactions")
    payment_session = db.relationship("PaymentSession", back_populates="transaction")

    def __repr__(self):
        return f"<Transaction {self.id} - {self.status} >"

 
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

    user = db.relationship("User", back_populates="payment_sessions")
    qr_code = db.relationship("QRCode", back_populates="payment_sessions")
    transaction = db.relationship("Transaction", back_populates="payment_session", uselist=False)

    def __repr__(self):
        return f"<PaymentSession {self.id} - {self.status}>"