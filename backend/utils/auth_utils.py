from datetime import datetime, timezone

from flask import current_app
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError, OperationalError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from extensions import db
from models import User, Vendor
from utils.reset_email_util import ResetEmail


VALID_SHORTCODE_TYPES = {"TILL", "PAYBILL"}


class AuthUtilError(Exception):
    """Structured auth error used by route handlers."""

    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class AuthUtill:
    """
    Utility layer for authentication operations.

    Routes should delegate all business and data-access logic to this class.
    """

    def _normalize_shortcode_type(self, raw_value):
        value = (raw_value or "TILL").strip().upper()
        if value not in VALID_SHORTCODE_TYPES:
            raise AuthUtilError("shortcode_type must be either TILL or PAYBILL", 400)
        return value

    def _normalize_identity_pk(self, identity):
        try:
            return int(identity)
        except (TypeError, ValueError):
            return identity

    def _build_user_token(self, user):
        return create_access_token(
            identity=str(user.id),
            additional_claims={
                "user_type": "user",
                "phone": user.phone_number,
                "email": user.email,
            },
        )

    def _build_vendor_token(self, vendor):
        return create_access_token(
            identity=str(vendor.id),
            additional_claims={
                "user_type": "vendor",
                "business_shortcode": vendor.business_shortcode,
                "shortcode_type": vendor.shortcode_type,
                "merchant_id": vendor.merchant_id,
                "phone": vendor.phone,
                "email": vendor.email,
            },
        )

    def register_user(self, data):
        if not isinstance(data, dict):
            raise AuthUtilError("Invalid or missing JSON payload", 400)

        required_fields = ["name", "phone_number", "email", "password"]
        for field in required_fields:
            if field not in data:
                raise AuthUtilError(f"Missing required field: {field}", 400)
            if not data[field]:
                raise AuthUtilError(f"Field {field} cannot be empty", 400)

        if not all(isinstance(data[field], str) for field in required_fields):
            raise AuthUtilError("Invalid field types in request payload", 400)

        name = data["name"].strip()
        phone_number = data["phone_number"].strip()
        email = data["email"].strip().lower()
        password = data["password"]

        if not email or "@" not in email:
            raise AuthUtilError("Invalid email format", 400)

        if len(phone_number) < 10:
            raise AuthUtilError("Invalid phone number", 400)

        if len(password) < 8:
            raise AuthUtilError("Password must be at least 8 characters long", 400)

        if User.query.filter_by(email=email).first():
            raise AuthUtilError("User with same email already exist", 409)

        if User.query.filter_by(phone_number=phone_number).first():
            raise AuthUtilError("User with the same phone number already exists", 409)

        try:
            new_user = User(name=name, phone_number=phone_number, email=email)
            new_user.set_password(password)

            db.session.add(new_user)
            db.session.commit()

            access_token = self._build_user_token(new_user)
            return {
                "message": "User registered successfully",
                "access_token": access_token,
                "user": {
                    "id": new_user.id,
                    "name": new_user.name,
                    "phone": new_user.phone_number,
                    "email": new_user.email,
                },
            }, 201
        except Exception as exc:
            db.session.rollback()
            raise AuthUtilError("Registration failed", 500, str(exc))

    def register_vendor(self, data):
        if not isinstance(data, dict):
            raise AuthUtilError("Invalid or missing JSON payload", 400)

        required_fields = [
            "name",
            "business_shortcode",
            "merchant_id",
            "mcc",
            "store_label",
            "email",
            "phone",
            "password",
        ]

        for field in required_fields:
            if field not in data:
                raise AuthUtilError(f"Missing required field: {field}", 400)
            if not data[field]:
                raise AuthUtilError(f"Field {field} cannot be empty", 400)

        email = data["email"].strip().lower()
        phone = data["phone"].strip()
        password = data["password"]
        business_shortcode = data["business_shortcode"].strip()

        if not email or "@" not in email:
            raise AuthUtilError("Invalid email format", 400)

        if len(phone) < 10:
            raise AuthUtilError("Invalid phone number", 400)

        if len(password) < 8:
            raise AuthUtilError("Password must be at least 8 characters", 400)

        mcc = data.get("mcc")
        if mcc and len(mcc.strip()) not in (4, 8):
            raise AuthUtilError("MCC must be 4 or 8 characters", 400)

        shortcode_type = self._normalize_shortcode_type(data.get("shortcode_type"))

        paybill_account_number = data.get("paybill_account_number")
        if paybill_account_number is not None:
            paybill_account_number = str(paybill_account_number).strip() or None
        if shortcode_type == "TILL":
            paybill_account_number = None

        if Vendor.query.filter_by(email=email).first():
            raise AuthUtilError("Vendor with this email already exists", 409)

        if Vendor.query.filter_by(business_shortcode=business_shortcode).first():
            raise AuthUtilError("Vendor with this business shortcode already exists", 409)

        if Vendor.query.filter_by(phone=phone).first():
            raise AuthUtilError("Vendor with this phone number already exists", 409)

        try:
            new_vendor = Vendor(
                name=data["name"].strip(),
                business_shortcode=business_shortcode,
                shortcode_type=shortcode_type,
                paybill_account_number=paybill_account_number,
                merchant_id=data["merchant_id"].strip(),
                mcc=data["mcc"].strip(),
                store_label=data["store_label"].strip(),
                email=email,
                phone=phone,
            )

            new_vendor.set_password(password)
            db.session.add(new_vendor)
            db.session.commit()

            access_token = self._build_vendor_token(new_vendor)
            return {
                "message": "Vendor registered successfully",
                "access_token": access_token,
                "vendor": {
                    "id": new_vendor.id,
                    "name": new_vendor.name,
                    "business_shortcode": new_vendor.business_shortcode,
                    "shortcode_type": new_vendor.shortcode_type,
                    "paybill_account_number": new_vendor.paybill_account_number,
                    "merchant_id": new_vendor.merchant_id,
                    "mcc": new_vendor.mcc,
                    "store_label": new_vendor.store_label,
                    "email": new_vendor.email,
                    "phone": new_vendor.phone,
                },
            }, 201
        except IntegrityError as exc:
            db.session.rollback()
            raw_message = str(getattr(exc, "orig", exc))
            lowered = raw_message.lower()
            if "vendors_pkey" in lowered:
                raise AuthUtilError(
                    "Vendor ID sequence is out of sync. Run sequence repair on vendors.id then retry.",
                    500,
                    raw_message,
                )
            raise AuthUtilError("Registration failed", 500, raw_message)
        except OperationalError as exc:
            db.session.rollback()
            raise AuthUtilError(
                "Temporary database connection issue. Please retry shortly.",
                503,
                str(getattr(exc, "orig", exc)),
            )
        except Exception as exc:
            db.session.rollback()
            raise AuthUtilError("Registration failed", 500, str(exc))

    def login(self, data):
        if not isinstance(data, dict):
            raise AuthUtilError("No data provided", 400)

        required_fields = ["email", "password"]
        for field in required_fields:
            if field not in data:
                raise AuthUtilError(f"Missing required field: {field}", 400)
            if not data[field]:
                raise AuthUtilError(f"Field {field} cannot be empty", 400)

        email = data.get("email", "").lower().strip()
        password = data.get("password")

        if "@" not in email:
            raise AuthUtilError("Invalid email format", 400)

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            access_token = self._build_user_token(user)
            return {
                "message": "Login successful",
                "access_token": access_token,
                "user_type": "user",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "phone": user.phone_number,
                },
            }, 200

        vendor = Vendor.query.filter_by(email=email).first()
        if vendor and vendor.check_password(password):
            vendor.last_login = datetime.now(timezone.utc)
            db.session.commit()

            access_token = self._build_vendor_token(vendor)
            return {
                "message": "Login successful",
                "access_token": access_token,
                "user_type": "vendor",
                "vendor": {
                    "id": vendor.id,
                    "name": vendor.name,
                    "business_shortcode": vendor.business_shortcode,
                    "shortcode_type": vendor.shortcode_type,
                    "paybill_account_number": vendor.paybill_account_number,
                    "merchant_id": vendor.merchant_id,
                    "mcc": vendor.mcc,
                    "store_label": vendor.store_label,
                    "email": vendor.email,
                    "phone": vendor.phone,
                    "psp_id": vendor.psp_id,
                    "psp_name": vendor.psp_name,
                },
            }, 200

        raise AuthUtilError("Invalid email or password", 401)

    def logout(self, identity, claims):
        user_type = claims.get("user_type")
        user_email = claims.get("email")
        identity_pk = self._normalize_identity_pk(identity)

        print(f"Logout: {user_type} ID {identity} ({user_email}) at {datetime.now(timezone.utc)}")

        if user_type == "user":
            entity = db.session.get(User, identity_pk)
            if entity:
                entity.last_logout = datetime.now(timezone.utc)
                db.session.commit()
        elif user_type == "vendor":
            entity = db.session.get(Vendor, identity_pk)
            if entity:
                entity.last_logout = datetime.now(timezone.utc)
                db.session.commit()

        return {
            "message": "Logged out successfully",
            "user_type": user_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, 200

    def _reset_serializer(self):
        secret = current_app.config.get("JWT_SECRET_KEY") or current_app.config.get("SECRET_KEY")
        if not secret:
            raise AuthUtilError("Server configuration error: missing secret key", 500)
        salt = current_app.config.get("PASSWORD_RESET_SALT", "password-reset-salt")
        return URLSafeTimedSerializer(secret_key=secret, salt=salt)

    def _password_reset_expires_seconds(self):
        return int(current_app.config.get("PASSWORD_RESET_EXPIRES_SECONDS", 3600))

    def forgot_password(self, data):
        if not isinstance(data, dict):
            raise AuthUtilError("Invalid or missing JSON payload", 400)

        email = str(data.get("email", "")).strip().lower()
        if not email:
            raise AuthUtilError("Email is required", 400)

        serializer = self._reset_serializer()
        reset_token = None

        user = User.query.filter_by(email=email).first()
        if user:
            reset_token = serializer.dumps({"sub": str(user.id), "user_type": "user", "email": user.email})

        if reset_token is None:
            vendor = Vendor.query.filter_by(email=email).first()
            if vendor:
                reset_token = serializer.dumps(
                    {"sub": str(vendor.id), "user_type": "vendor", "email": vendor.email}
                )

        # Send the email when an account exists, but keep endpoint response generic.
        if reset_token:
            reset_url = (current_app.config.get("PASSWORD_RESET_FRONTEND_URL") or "").strip()
            email_sender = ResetEmail(
                reset_url=reset_url,
                token=reset_token,
                recipient_email=email,
            )
            send_result = email_sender.send_reset_email()
            if send_result is not True:
                current_app.logger.warning(send_result)

        response = {
            "message": "If the account exists, a password reset token has been generated.",
            "expires_in_seconds": self._password_reset_expires_seconds(),
        }

        expose_token = bool(current_app.config.get("EXPOSE_RESET_TOKEN", False))
        if reset_token and expose_token:
            response["reset_token"] = reset_token

        return response, 200

    def reset_password(self, data):
        if not isinstance(data, dict):
            raise AuthUtilError("Invalid or missing JSON payload", 400)

        token = str(data.get("token", "")).strip()
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not token:
            raise AuthUtilError("Reset token is required", 400)

        if not isinstance(new_password, str) or not new_password:
            raise AuthUtilError("new_password is required", 400)

        if len(new_password) < 8:
            raise AuthUtilError("Password must be at least 8 characters", 400)

        if confirm_password is not None and new_password != confirm_password:
            raise AuthUtilError("Passwords do not match", 400)

        serializer = self._reset_serializer()

        try:
            payload = serializer.loads(token, max_age=self._password_reset_expires_seconds())
        except SignatureExpired:
            raise AuthUtilError("Reset token has expired", 400)
        except BadSignature:
            raise AuthUtilError("Invalid reset token", 400)

        subject_id = self._normalize_identity_pk(payload.get("sub"))
        user_type = payload.get("user_type")
        token_email = payload.get("email")

        if not subject_id or user_type not in {"user", "vendor"}:
            raise AuthUtilError("Invalid reset token payload", 400)

        if user_type == "user":
            entity = db.session.get(User, subject_id)
        else:
            entity = db.session.get(Vendor, subject_id)

        if not entity or entity.email.lower() != str(token_email).lower():
            raise AuthUtilError("Invalid reset token", 400)

        entity.set_password(new_password)
        db.session.commit()

        return {"message": "Password reset successful"}, 200
