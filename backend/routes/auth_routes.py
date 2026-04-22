from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from utils.auth_utils import AuthUtill, AuthUtilError
from extensions import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
auth_util = AuthUtill()


def _error_response(exc):
    payload = {"error": exc.message}
    if exc.details:
        payload["details"] = exc.details
    return jsonify(payload), exc.status_code


@auth_bp.route("/register/user", methods=["POST"])
@limiter.limit("3 per minute")
def register_user():
    try:
        data = request.get_json(silent=True)
        response, status = auth_util.register_user(data)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Registration failed", "details": str(exc)}), 500


@auth_bp.route("/register/vendor", methods=["POST"])
@limiter.limit("3 per minute")
def register_vendor():
    try:
        data = request.get_json(silent=True)
        response, status = auth_util.register_vendor(data)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Registration failed", "details": str(exc)}), 500


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("8 per minute")
def login():
    try:
        data = request.get_json(silent=True)
        response, status = auth_util.login(data)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Login failed", "details": str(exc)}), 500


@auth_bp.route("/logout", methods=["POST"])
@limiter.limit("30 per minute")
@jwt_required()
def logout():
    try:
        identity = get_jwt_identity()
        claims = get_jwt()
        response, status = auth_util.logout(identity, claims)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Logout failed", "details": str(exc)}), 500


@auth_bp.route("/forgot-password", methods=["POST"])
@limiter.limit("3 per 10 minute")
def forgot_password():
    try:
        data = request.get_json(silent=True)
        response, status = auth_util.forgot_password(data)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Forgot password failed", "details": str(exc)}), 500


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("5 per 10 minute")
def reset_password():
    try:
        data = request.get_json(silent=True)
        response, status = auth_util.reset_password(data)
        return jsonify(response), status
    except AuthUtilError as exc:
        return _error_response(exc)
    except Exception as exc:
        return jsonify({"error": "Reset password failed", "details": str(exc)}), 500
