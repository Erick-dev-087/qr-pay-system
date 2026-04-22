from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text
from extensions import db, jwt, migrate, limiter
from config import (DatabaseConfigs, FlaskConfigs, 
                    JWTConfig, PasswordResetConfig, EmailConfig, RateLimitConfig)
from routes import auth_bp, user_bp, vendor_bp, qr_bp, payment_bp, admin_bp

import os



def create_app():
    """
    Application Factory Pattern
    Creates and configures the Flask application instance
    """
    app = Flask(__name__)
    CORS(app)
    
    # Load database configuration
    db_uri = DatabaseConfigs.SQLALCHEMY_DATABASE_URL
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = DatabaseConfigs.SQLALCHEMY_TRACK_MODIFICATIONS
    if not str(db_uri).startswith('sqlite:'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = DatabaseConfigs.SQLALCHEMY_ENGINE_OPTIONS
    
    # Load Flask configuration
    app.config['SECRET_KEY'] = FlaskConfigs.SECRET_KEY
    app.config['DEBUG'] = FlaskConfigs.DEBUG
    app.config['JWT_SECRET_KEY'] = JWTConfig.JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = JWTConfig.JWT_ACCESS_TOKEN_EXPIRES
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = JWTConfig.JWT_REFRESH_TOKEN_EXPIRES
    app.config['JWT_TOKEN_LOCATION'] = JWTConfig.JWT_TOKEN_LOCATION
    app.config['JWT_HEADER_NAME'] = JWTConfig.JWT_HEADER_NAME
    app.config['JWT_HEADER_TYPE'] = JWTConfig.JWT_HEADER_TYPE
    app.config['PASSWORD_RESET_SALT'] = PasswordResetConfig.PASSWORD_RESET_SALT
    app.config['PASSWORD_RESET_EXPIRES_SECONDS'] = PasswordResetConfig.PASSWORD_RESET_EXPIRES_SECONDS
    app.config['EXPOSE_RESET_TOKEN'] = PasswordResetConfig.EXPOSE_RESET_TOKEN
    app.config['PASSWORD_RESET_FRONTEND_URL'] = PasswordResetConfig.PASSWORD_RESET_FRONTEND_URL
    app.config['MAIL_BACKEND'] = EmailConfig.MAIL_BACKEND
    app.config['MAIL_SERVER'] = EmailConfig.MAIL_SERVER
    app.config['MAIL_PORT'] = EmailConfig.MAIL_PORT
    app.config['MAIL_USE_TLS'] = EmailConfig.MAIL_USE_TLS
    app.config['MAIL_USE_SSL'] = EmailConfig.MAIL_USE_SSL
    app.config['MAIL_USERNAME'] =  EmailConfig.MAIL_USERNAME
    app.config['MAIL_PASSWORD'] = EmailConfig.MAIL_PASSWORD
    app.config['MAIL_DEFAULT_SENDER'] = EmailConfig.MAIL_DEFAULT_SENDER
    app.config['MAIL_TIMEOUT_SECONDS'] = EmailConfig.MAIL_TIMEOUT_SECONDS
    app.config['MAIL_SEND_MAX_RETRIES'] = EmailConfig.MAIL_SEND_MAX_RETRIES
    app.config['MAIL_RETRY_BACKOFF_SECONDS'] = EmailConfig.MAIL_RETRY_BACKOFF_SECONDS
    app.config['RATELIMIT_STORAGE_URI'] = RateLimitConfig.RATELIMIT_STORAGE_URI
    app.config['RATELIMIT_HEADERS_ENABLED'] = RateLimitConfig.RATELIMIT_ENABLE_HEADERS
    
    
    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    
    # Import models to register them with Flask-Migrate
    from models import User, Vendor, Transaction, QRCode, ScanLog, PaymentSession

    
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            print("✅ Database is running and connection was verified successfully!")
        except Exception as exc:
            print(f"❌ Database connection check failed: {exc}")
            raise

    # JWT User Identity Loaders
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """
        Callback to convert user object to identity (what goes into token)
        Returns user ID to be stored in JWT token
        """
        # Handle both objects (User/Vendor) and plain IDs (int)
        if isinstance(user, (int, str)):
            return user
        return user.id
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """
        Callback to load user from JWT token identity
        Returns user object from database based on token identity
        """
        identity = jwt_data["sub"]  # "sub" is the identity
        # Try to find user first, then vendor
        user = User.query.filter_by(id=identity).first()
        if user:
            return user
        return Vendor.query.filter_by(id=identity).first()
    
    print("✅ JWT configured successfully!")
    
    #Registering Blueprints
    app.register_blueprint(auth_bp,url_prefix='/api/auth')
    app.register_blueprint(admin_bp,url_prefix='/api/admin')
    app.register_blueprint(payment_bp, url_prefix='/api/payment')
    app.register_blueprint(qr_bp, url_prefix='/api/qr')
    app.register_blueprint(user_bp,url_prefix='/api/user')
    app.register_blueprint(vendor_bp, url_prefix='/api/merchant')
    
    
    
    print("Blueprints registered successfully!")
    
    @app.route('/api/health', methods=['GET'])
    @limiter.limit('120 per minute')
    def health_check():
        """
        Health check endpoint for testing backend connectivity.
        Used by Android app to verify it can reach the backend.

        Response:
        {
            "status": "ok",
            "message": "QR Pay System backend is running",
            "version": "1.0.0"
        }
        """
        return jsonify({
            "status": "ok",
            "message": "QR Pay System backend is running",
            "version": "1.0.0"
        }), 200

    @app.errorhandler(429)
    def rate_limit_exceeded(_error):
        return jsonify({
            'error': 'Too many requests',
            'message': 'Rate limit exceeded. Please try again shortly.'
        }), 429

    return app

# Create app instance for running
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
 