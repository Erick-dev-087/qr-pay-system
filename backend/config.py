import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _normalize_database_url(raw_url: str | None) -> str:
    """Normalize DATABASE_URL for SQLAlchemy/psycopg2 compatibility."""
    if not raw_url:
        raise ValueError("DATABASE_URL must be set in environment variables")

    db_url = raw_url.strip().strip('"').strip("'")

    # Some providers still expose postgres://; SQLAlchemy expects postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Optional override for providers that require SSL (for example, DB_SSLMODE=require)
    db_sslmode = os.getenv("DB_SSLMODE", "").strip()
    if db_sslmode and "sslmode=" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{separator}sslmode={db_sslmode}"

    return db_url


class DatabaseConfigs():
    """Database Settings"""

    SQLALCHEMY_DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30")),
    }

class FlaskConfigs():
    """ Flask settings """
    DEBUG = _as_bool(os.getenv("DEBUG"), True)
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")

    
class DarajaAPIConfigs():
    """Daraja API settings"""
    DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY")
    DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET")
    DARAJA_BASE_URL = os.getenv("DARAJA_BASE_URL","https://sandbox.safaricom.co.ke")
    DARAJA_SHORTCODE = os.getenv("DARAJA_SHORTCODE")
    DARAJA_PASSKEY = os.getenv("DARAJA_PASSKEY")
    DARAJA_CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "https://yourdomain.com/confirm")

    @classmethod
    def validate(cls):
        debug_mode = os.getenv("DEBUG", "True") == "True"
        if not debug_mode:
            if not cls.DARAJA_CONSUMER_KEY:
                raise ValueError("DARAJA_CONSUMER_KEY must be set in production")
            if not cls.DARAJA_CONSUMER_SECRET:
                raise ValueError("DARAJA_CONSUMER_SECRET must be set in production")
            if cls.DARAJA_BASE_URL == "https://sandbox.safaricom.co.ke":
                raise ValueError("Must use production Daraja URL in production")

class QRconfig():
    """ Static QR Codes Configs"""
    STATIC_QR_MODE = _as_bool(os.getenv("STATIC_QR_MODE"), False)

class SecurityConfig:
    """ Cookies security Configs"""
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = int(os.getenv("SESSION_LIFETIME", "1800"))

class JWTConfig:
    """JWT Authentication Configs"""
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")

    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600")) #Expires after an hour
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "2592000")) # Expires in 30 days

    JWT_TOKEN_LOCATION = ["headers"] #Look in Authorization header

    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer" 

    JWT_ERROR_MESSAGE_KEY = "message"

    JWT_ALGORITH = "HS256"


class PasswordResetConfig:
    """Password reset token settings."""

    PASSWORD_RESET_SALT = os.getenv("PASSWORD_RESET_SALT", "qr-pay-password-reset-salt")
    PASSWORD_RESET_EXPIRES_SECONDS = int(os.getenv("PASSWORD_RESET_EXPIRES_SECONDS", "3600"))
    EXPOSE_RESET_TOKEN = _as_bool(os.getenv("EXPOSE_RESET_TOKEN"), False)
    PASSWORD_RESET_FRONTEND_URL = (os.getenv("PASSWORD_RESET_FRONTEND_URL") or "").strip()

    
class EmailConfig:
    """Email Sending Configs"""
    MAIL_BACKEND = (os.getenv("MAIL_BACKEND") or "smtp").strip().lower()
    MAIL_SERVER = (os.getenv("MAIL_SERVER") or "").strip()
    MAIL_PORT = int((os.getenv("MAIL_PORT") or "0").strip() or 0)
    MAIL_USE_TLS = _as_bool(os.getenv("MAIL_USE_TLS"), True)
    MAIL_USE_SSL = _as_bool(os.getenv("MAIL_USE_SSL"), False)
    MAIL_USERNAME = (os.getenv("MAIL_USERNAME") or "").strip()
    MAIL_PASSWORD = (os.getenv("MAIL_PASSWORD") or "").strip()
    MAIL_DEFAULT_SENDER = (os.getenv("MAIL_DEFAULT_SENDER") or "").strip()
    MAIL_TIMEOUT_SECONDS = int((os.getenv("MAIL_TIMEOUT_SECONDS") or "20").strip() or 20)
    MAIL_SEND_MAX_RETRIES = int((os.getenv("MAIL_SEND_MAX_RETRIES") or "3").strip() or 3)
    MAIL_RETRY_BACKOFF_SECONDS = float(
        (os.getenv("MAIL_RETRY_BACKOFF_SECONDS") or "1").strip() or 1
    )