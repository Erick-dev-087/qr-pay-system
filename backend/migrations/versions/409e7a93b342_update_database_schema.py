"""Baseline schema + seed data for QR Pay backend.

Revision ID: 409e7a93b342
Revises:
Create Date: 2025-11-01 16:07:06.329089

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash


# revision identifiers, used by Alembic.
revision = "409e7a93b342"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    transaction_status = sa.Enum(
        "PENDING", "SUCCESS", "FAILED", "CANCELLED", name="transactionstatus"
    )
    transaction_type = sa.Enum("INCOMING", "OUTGOING", name="transactiontype")
    outflow_reason = sa.Enum(
        "REFUND",
        "TRANSFER",
        "PAYOUT",
        "SETTLEMENT",
        "PLATFORM_FEE",
        "ADJUSTMENT",
        name="outflowreason",
    )
    qr_status = sa.Enum("ACTIVE", "INACTIVE", "EXPIRED", name="qrstatus")
    qr_type = sa.Enum("STATIC", "DYNAMIC", name="qr_type")
    scan_status = sa.Enum(
        "SCANNED_ONLY",
        "PAYMENT_INITIATED",
        "PAYMENT_SUCCESS",
        "PAYMENT_FAILED",
        name="scanstatus",
    )
    payment_status = sa.Enum(
        "PAYMENT_INITIATED", "PAYMENT_PENDING", "PAYMENT_EXPIRED", name="paymentstatus"
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone_number", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("phone_number", name="uq_user_phone_number"),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )

    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("business_name", sa.String(length=150), nullable=True),
        sa.Column("business_shortcode", sa.String(length=20), nullable=False),
        sa.Column("merchant_id", sa.String(length=100), nullable=True),
        sa.Column("mcc", sa.String(length=8), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("store_label", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("psp_id", sa.String(length=100), nullable=True),
        sa.Column("psp_name", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.UniqueConstraint("email", name="uq_vendor_email"),
        sa.UniqueConstraint("phone", name="uq_vendor_phone"),
        sa.UniqueConstraint("business_shortcode", name="uq_vendor_business_shortcode"),
    )

    op.create_table(
        "qr_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payload_data", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("qr_type", qr_type, nullable=False),
        sa.Column("status", qr_status, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=True),
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column("status", transaction_status, nullable=False),
        sa.Column("outflow_reason", outflow_reason, nullable=True),
        sa.Column("mpesa_receipt", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("callback_response", sa.JSON(), nullable=True),
        sa.Column("initated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=True),
        sa.Column("qrcode_id", sa.Integer(), sa.ForeignKey("qr_codes.id"), nullable=True),
    )
    op.create_index(
        "ix_transactions_mpesa_receipt", "transactions", ["mpesa_receipt"], unique=False
    )

    op.create_table(
        "scanlogs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", scan_status, nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("qr_id", sa.Integer(), sa.ForeignKey("qr_codes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )

    op.create_table(
        "payment_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("expired_at", sa.DateTime(), nullable=True),
        sa.Column("qr_id", sa.Integer(), sa.ForeignKey("qr_codes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=True),
    )

    now = datetime.now(timezone.utc)

    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("phone_number", sa.String),
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": 1,
                "name": "Alice User",
                "phone_number": "+254700000001",
                "email": "alice.user@example.com",
                "password_hash": generate_password_hash("Pass1234!"),
                "created_at": now,
                "updated_at": now,
                "is_active": True,
            },
            {
                "id": 2,
                "name": "Bob User",
                "phone_number": "+254700000002",
                "email": "bob.user@example.com",
                "password_hash": generate_password_hash("Pass1234!"),
                "created_at": now,
                "updated_at": now,
                "is_active": True,
            },
        ],
    )

    vendors = sa.table(
        "vendors",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("business_name", sa.String),
        sa.column("business_shortcode", sa.String),
        sa.column("merchant_id", sa.String),
        sa.column("mcc", sa.String),
        sa.column("country_code", sa.String),
        sa.column("currency_code", sa.String),
        sa.column("store_label", sa.String),
        sa.column("email", sa.String),
        sa.column("phone", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("psp_id", sa.String),
        sa.column("psp_name", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        vendors,
        [
            {
                "id": 1,
                "name": "Merchant One",
                "business_name": "Merchant One Store",
                "business_shortcode": "123456",
                "merchant_id": "MRC001",
                "mcc": "5411",
                "country_code": "KE",
                "currency_code": "404",
                "store_label": "Nairobi CBD",
                "email": "merchant1@example.com",
                "phone": "+254711000001",
                "password_hash": generate_password_hash("Vendor1234!"),
                "psp_id": "PSP001",
                "psp_name": "Demo PSP",
                "created_at": now,
                "updated_at": now,
                "is_active": True,
            },
            {
                "id": 2,
                "name": "Merchant Two",
                "business_name": "Merchant Two Shop",
                "business_shortcode": "654321",
                "merchant_id": "MRC002",
                "mcc": "5812",
                "country_code": "KE",
                "currency_code": "404",
                "store_label": "Westlands",
                "email": "merchant2@example.com",
                "phone": "+254711000002",
                "password_hash": generate_password_hash("Vendor1234!"),
                "psp_id": "PSP002",
                "psp_name": "Demo PSP",
                "created_at": now,
                "updated_at": now,
                "is_active": True,
            },
        ],
    )

    qr_codes = sa.table(
        "qr_codes",
        sa.column("id", sa.Integer),
        sa.column("payload_data", sa.Text),
        sa.column("payload_json", sa.JSON),
        sa.column("qr_type", sa.String),
        sa.column("status", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("vendor_id", sa.Integer),
        sa.column("currency_code", sa.String),
        sa.column("reference_number", sa.String),
        sa.column("last_scanned_at", sa.DateTime),
    )
    op.bulk_insert(
        qr_codes,
        [
            {
                "id": 1,
                "payload_data": "EMVCO|M1|123456",
                "payload_json": {"merchant": "Merchant One", "shortcode": "123456"},
                "qr_type": "STATIC",
                "status": "ACTIVE",
                "created_at": now,
                "vendor_id": 1,
                "currency_code": "404",
                "reference_number": "REF-QR-0001",
                "last_scanned_at": now,
            },
            {
                "id": 2,
                "payload_data": "EMVCO|M2|654321",
                "payload_json": {"merchant": "Merchant Two", "shortcode": "654321"},
                "qr_type": "DYNAMIC",
                "status": "ACTIVE",
                "created_at": now,
                "vendor_id": 2,
                "currency_code": "404",
                "reference_number": "REF-QR-0002",
                "last_scanned_at": now,
            },
        ],
    )

    transactions = sa.table(
        "transactions",
        sa.column("id", sa.Integer),
        sa.column("amount", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("type", sa.String),
        sa.column("status", sa.String),
        sa.column("outflow_reason", sa.String),
        sa.column("mpesa_receipt", sa.String),
        sa.column("phone", sa.String),
        sa.column("callback_response", sa.JSON),
        sa.column("initated_at", sa.DateTime),
        sa.column("completed_at", sa.DateTime),
        sa.column("user_id", sa.Integer),
        sa.column("vendor_id", sa.Integer),
        sa.column("qrcode_id", sa.Integer),
    )
    op.bulk_insert(
        transactions,
        [
            {
                "id": 1,
                "amount": 150,
                "currency": "404",
                "type": "INCOMING",
                "status": "SUCCESS",
                "outflow_reason": None,
                "mpesa_receipt": "MPESA-0001",
                "phone": "+254700000001",
                "callback_response": {"result": "ok", "code": 0},
                "initated_at": now,
                "completed_at": now,
                "user_id": 1,
                "vendor_id": 1,
                "qrcode_id": 1,
            },
            {
                "id": 2,
                "amount": 300,
                "currency": "404",
                "type": "OUTGOING",
                "status": "PENDING",
                "outflow_reason": "TRANSFER",
                "mpesa_receipt": "MPESA-0002",
                "phone": "+254711000002",
                "callback_response": {"result": "pending", "code": 1},
                "initated_at": now,
                "completed_at": now,
                "user_id": None,
                "vendor_id": 2,
                "qrcode_id": 2,
            },
        ],
    )

    scanlogs = sa.table(
        "scanlogs",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("timestamp", sa.DateTime),
        sa.column("qr_id", sa.Integer),
        sa.column("user_id", sa.Integer),
    )
    op.bulk_insert(
        scanlogs,
        [
            {"id": 1, "status": "SCANNED_ONLY", "timestamp": now, "qr_id": 1, "user_id": 1},
            {"id": 2, "status": "PAYMENT_SUCCESS", "timestamp": now, "qr_id": 2, "user_id": 2},
        ],
    )

    payment_sessions = sa.table(
        "payment_sessions",
        sa.column("id", sa.Integer),
        sa.column("amount", sa.Integer),
        sa.column("status", sa.String),
        sa.column("started_at", sa.DateTime),
        sa.column("expired_at", sa.DateTime),
        sa.column("qr_id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("transaction_id", sa.Integer),
    )
    op.bulk_insert(
        payment_sessions,
        [
            {
                "id": 1,
                "amount": 150,
                "status": "PAYMENT_PENDING",
                "started_at": now,
                "expired_at": now,
                "qr_id": 1,
                "user_id": 1,
                "transaction_id": 1,
            },
            {
                "id": 2,
                "amount": 300,
                "status": "PAYMENT_INITIATED",
                "started_at": now,
                "expired_at": now,
                "qr_id": 2,
                "user_id": 2,
                "transaction_id": 2,
            },
        ],
    )


def downgrade():
    op.drop_table("payment_sessions")
    op.drop_table("scanlogs")
    op.drop_index("ix_transactions_mpesa_receipt", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("qr_codes")
    op.drop_table("vendors")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS scanstatus")
    op.execute("DROP TYPE IF EXISTS qr_type")
    op.execute("DROP TYPE IF EXISTS qrstatus")
    op.execute("DROP TYPE IF EXISTS outflowreason")
    op.execute("DROP TYPE IF EXISTS transactiontype")
    op.execute("DROP TYPE IF EXISTS transactionstatus")
