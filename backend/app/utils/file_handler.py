import os
import uuid
from werkzeug.utils import secure_filename
from app.utils.security import sanitize_filename
from app.utils.logger import get_logger

logger = get_logger(__name__)


def save_uploaded_file(file, upload_folder='uploads'):
    """Save an uploaded file and return its path"""
    try:
        # Create upload folder if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        filename = sanitize_filename(filename)
        
        # Add UUID to ensure uniqueness
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
        
        # Save file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Get file info
        file_size = os.path.getsize(file_path)
        file_type = ext[1:].lower() if ext else ''
        
        return file_path, file_type, file_size
        
    except Exception as e:
        logger.error(f"Error saving uploaded file: {str(e)}")
        return None, None, None


def delete_file(file_path):
    """Delete a file"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return False


def get_file_size(file_path):
    """Get the size of a file in bytes"""
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error getting file size: {str(e)}")
        return 0


def is_allowed_file(filename, allowed_extensions):
    """Check if a file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions