import os
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(raw_url: str) -> str:
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

class FlaskConfigs():
    """ Flask settings """
    DEBUG = os.getenv("DEBUG", "True") == "True"
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
    STATIC_QR_MODE = os.getenv("STATIC_QR_MODE","False") == "True"

class SecurityConfig:
    """ Cookies security Configs"""
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False") == "True"
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

    
