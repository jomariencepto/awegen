import hashlib
import bcrypt
from app.utils.logger import get_logger

logger = get_logger(__name__)


def hash_password_bcrypt(password):
    """Hash a password using bcrypt"""
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        return None


def verify_password_bcrypt(password, hashed_password):
    """Verify a password against its bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False


def hash_sha256(data):
    """Hash data using SHA-256"""
    try:
        return hashlib.sha256(data.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Error hashing data: {str(e)}")
        return None