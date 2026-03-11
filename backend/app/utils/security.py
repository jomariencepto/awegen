import random
import string
from datetime import datetime, timedelta
import hashlib
import secrets
from app.utils.logger import get_logger

logger = get_logger(__name__)


def generate_otp(length=6):
    """Generate a random OTP"""
    digits = string.digits
    otp = ''.join(random.choice(digits) for _ in range(length))
    return otp


def generate_token(length=32):
    """Generate a random token"""
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(length))
    return token


def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    return hash_password(password) == hashed_password


def send_otp_email(email, otp, purpose):
    """Send OTP via email (placeholder implementation)"""
    try:
        # In a real implementation, you would use an email service
        logger.info(f"Sending OTP {otp} to {email} for {purpose}")
        
        # Placeholder for email sending logic
        # Example:
        # from app.utils.email import send_email
        # subject = f"Your OTP for {purpose}"
        # body = f"Your OTP is: {otp}"
        # send_email(email, subject, body)
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending OTP email: {str(e)}")
        return False


def is_valid_email(email):
    """Check if an email is valid"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_filename(filename):
    """Sanitize a filename to prevent directory traversal"""
    # Remove path components
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove potentially dangerous characters
    filename = ''.join(c for c in filename if c.isalnum() or c in ['.', '_', '-'])
    
    # Ensure filename is not empty
    if not filename:
        filename = 'file'
    
    return filename