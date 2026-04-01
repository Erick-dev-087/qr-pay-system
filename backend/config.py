import os
from dotenv import load_dotenv

load_dotenv()


class DatabaseConfigs():
    """Database Settings"""
    
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        raise ValueError("DATABASE_URL must be set in environment variables")
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

    
