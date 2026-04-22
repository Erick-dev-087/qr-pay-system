"""
Database and other Flask extensions initialization
This module prevents circular imports by providing a central place
for extension objects that can be imported by both app.py and models.py
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize SQLAlchemy without binding to an app
# The app binding happens later in app.py using db.init_app(app)
db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()


def _rate_limit_key() -> str:
	"""Prefer authenticated identity; fallback to client IP for public routes."""
	try:
		verify_jwt_in_request(optional=True)
		identity = get_jwt_identity()
		if identity is not None:
			return f"user:{identity}"
	except Exception:
		pass

	return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=_rate_limit_key, default_limits=[])