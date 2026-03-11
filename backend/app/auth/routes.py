from flask import Blueprint, request, jsonify, current_app, make_response
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from flask_jwt_extended.exceptions import JWTExtendedException
import logging

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _get_limiter():
    """Lazy-fetch the Limiter instance attached to the current app."""
    return getattr(current_app, 'limiter', None)


@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        from app.auth.service import AuthService
        data = request.get_json()

        result, status_code = AuthService.register_user(data)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Internal server error during registration'
        }), 500


@auth_bp.route('/verify-otp', methods=['POST', 'OPTIONS'])
def verify_otp():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        from app.auth.service import AuthService
        data = request.get_json()

        if not data or 'email' not in data or 'otp_code' not in data:
            return jsonify({'success': False, 'message': 'Email and OTP required'}), 400

        result, status_code = AuthService.verify_otp(data)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"OTP verification error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    # Rate limit: max 10 attempts per minute per IP
    limiter = _get_limiter()
    if limiter:
        try:
            limiter.check()
        except Exception:
            return jsonify({
                'success': False,
                'message': 'Too many login attempts. Please wait and try again.'
            }), 429

    try:
        from app.auth.service import AuthService
        data = request.get_json()

        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'success': False, 'message': 'Email and password required'}), 400

        # Validate credentials via Service
        result, status_code = AuthService.login_user(data)

        # If login successful, generate tokens and set httpOnly cookies
        if status_code == 200 and result.get('success'):
            user_dict = result.get('user', {})
            user_id = user_dict.get('user_id')

            access_token = create_access_token(identity=str(user_id))
            refresh_token = create_refresh_token(identity=str(user_id))

            # Still include access_token in body for backward compatibility
            # (frontend will transition to cookies; header fallback remains)
            result['access_token'] = access_token

            resp = make_response(jsonify(result), status_code)
            set_access_cookies(resp, access_token)
            set_refresh_cookies(resp, refresh_token)
            return resp

        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@auth_bp.route('/request-otp', methods=['POST', 'OPTIONS'])
def request_otp():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        from app.auth.service import AuthService
        data = request.get_json()

        if not data or 'email' not in data:
            return jsonify({'success': False, 'message': 'Email required'}), 400

        result, status_code = AuthService.request_otp(data)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"OTP request error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@auth_bp.route('/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        from app.auth.service import AuthService
        data = request.get_json()

        required_fields = ['email', 'otp_code', 'new_password']
        missing = [f for f in required_fields if f not in data]

        if missing:
            return jsonify({'success': False, 'message': f'Missing: {", ".join(missing)}'}), 400

        result, status_code = AuthService.reset_password(data)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Password reset error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        from app.auth.models import User

        user_id = get_jwt_identity()

        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid token identity'}), 400

        user = User.query.get(user_id)

        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        return jsonify({
            'success': True,
            'user': user.to_dict()
        }), 200

    except Exception as e:
        logger.error(f"Get current user error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({'success': True, 'message': 'Logout successful'}), 200)
    unset_jwt_cookies(resp)
    return resp


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using the refresh cookie."""
    try:
        user_id = get_jwt_identity()
        new_access_token = create_access_token(identity=str(user_id))

        resp = make_response(jsonify({
            'success': True,
            'access_token': new_access_token,
        }), 200)
        set_access_cookies(resp, new_access_token)
        return resp
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Token refresh failed'}), 401


@auth_bp.route('/health', methods=['GET'])
def health():
    return jsonify({
        'success': True,
        'message': 'Auth service is running'
    }), 200
