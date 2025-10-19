from flask import Flask
from extensions import db
from config import DatabaseConfigs, FlaskConfigs

def create_app():
    """
    Application Factory Pattern
    Creates and configures the Flask application instance
    """
    app = Flask(__name__)
    
    # Load database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = DatabaseConfigs.SQLALCHEMY_DATABASE_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = DatabaseConfigs.SQLALCHEMY_TRACK_MODIFICATIONS
    
    # Load Flask configuration
    app.config['SECRET_KEY'] = FlaskConfigs.SECRET_KEY
    app.config['DEBUG'] = FlaskConfigs.DEBUG
    
    # Initialize database extension with app
    db.init_app(app)
    
    # Import models and create tables within app context
    with app.app_context():
        # Import models here to avoid circular imports
        from models import User, Vendor, Transaction, QRCode, ScanLog, PaymentSession
        
        # Create all database tables
        db.create_all()
        print("✅ Database tables created successfully!")
    
    # TODO: Register blueprints/routes here
    # from routes import main_bp
    # app.register_blueprint(main_bp)
    
    return app

# Create app instance for running
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
 