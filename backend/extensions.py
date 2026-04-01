"""
Database and other Flask extensions initialization
This module prevents circular imports by providing a central place
for extension objects that can be imported by both app.py and models.py
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

# Initialize SQLAlchemy without binding to an app
# The app binding happens later in app.py using db.init_app(app)
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()
