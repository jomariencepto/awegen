from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.utils.logger import get_logger

logger = get_logger(__name__)


def jwt_required_custom(fn):
    """Custom JWT required decorator"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"JWT verification failed: {str(e)}")
            return jsonify({'success': False, 'message': 'Invalid or expired token'}), 401
    return wrapper