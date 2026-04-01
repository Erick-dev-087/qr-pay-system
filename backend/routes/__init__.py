"""
Routes Package
Exports all blueprints for easy import in app.py
"""

from .auth_routes import auth_bp
from .admin_routes import admin_bp
from .payment_routes import payment_bp
from .qr_routes import qr_bp
from .user_routes import user_bp
from .vendor_routes import vendor_bp


__all__=['auth_bp','admin_bp','payment_bp',
         'qr_bp', 'user_bp','vendor_bp']

