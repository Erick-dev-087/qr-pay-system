import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfigs():
    """Database Settings"""
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL","sqlite:///qr_payment.db")
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


    
