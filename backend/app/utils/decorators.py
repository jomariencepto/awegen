from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.auth.models import User
from app.utils.logger import get_logger

logger = get_logger(__name__)


def role_required(roles):
    """
    Decorator to check if user has required role
    
    Args:
        roles: List of allowed role names (case-insensitive)
    
    Usage:
        @role_required(['teacher', 'admin'])
        def my_route():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                user_id = get_jwt_identity()
                
                if not user_id:
                    logger.warning("No user identity found in JWT")
                    return jsonify({'success': False, 'message': 'Authentication required'}), 401
                
                user = User.query.get(user_id)
                
                if not user:
                    logger.warning(f"User {user_id} not found in database")
                    return jsonify({'success': False, 'message': 'User not found'}), 404
                
                # user.role is already a string in your database
                user_role = user.role.lower() if user.role else ''
                
                # Normalize roles list to lowercase for comparison
                allowed_roles = [r.lower() for r in roles]
                
                logger.debug(f"User {user_id} has role '{user_role}', checking against {allowed_roles}")
                
                if user_role not in allowed_roles:
                    logger.warning(f"User {user_id} with role '{user_role}' attempted to access route requiring {allowed_roles}")
                    return jsonify({
                        'success': False,
                        'message': 'Insufficient permissions',
                        'required_roles': roles,
                        'user_role': user.role
                    }), 403
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Role check failed: {str(e)}", exc_info=True)
                return jsonify({
                    'success': False,
                    'message': 'Authorization failed',
                    'error': str(e)
                }), 500
                
        return decorated_function
    return decorator


def admin_required(f):
    """
    Decorator to check if user is admin
    
    Usage:
        @admin_required
        def my_route():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            
            if not user_id:
                logger.warning("No user identity found in JWT")
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return jsonify({'success': False, 'message': 'User not found'}), 404
            
            # user.role is already a string
            if user.role.lower() != 'admin':
                logger.warning(f"User {user_id} with role '{user.role}' attempted to access admin-only route")
                return jsonify({
                    'success': False,
                    'message': 'Admin access required',
                    'user_role': user.role
                }), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Admin check failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': 'Authorization failed',
                'error': str(e)
            }), 500
            
    return decorated_function


def teacher_required(f):
    """
    Decorator to check if user is teacher (or admin)
    
    Usage:
        @teacher_required
        def my_route():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            
            if not user_id:
                logger.warning("No user identity found in JWT")
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return jsonify({'success': False, 'message': 'User not found'}), 404
            
            # user.role is already a string
            # Allow both teacher and admin
            user_role = user.role.lower() if user.role else ''
            if user_role not in ['teacher', 'admin']:
                logger.warning(f"User {user_id} with role '{user.role}' attempted to access teacher-only route")
                return jsonify({
                    'success': False,
                    'message': 'Teacher access required',
                    'user_role': user.role
                }), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Teacher check failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': 'Authorization failed',
                'error': str(e)
            }), 500
            
    return decorated_function


def department_head_required(f):
    """
    Decorator to check if user is department head (or admin)
    Supports both 'department_head' and 'department' as role names
    
    Usage:
        @department_head_required
        def my_route():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            
            if not user_id:
                logger.warning("No user identity found in JWT")
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return jsonify({'success': False, 'message': 'User not found'}), 404
            
            # user.role is already a string
            # Support multiple role names for department heads
            user_role = user.role.lower() if user.role else ''
            if user_role not in ['department_head', 'department', 'admin']:
                logger.warning(f"User {user_id} with role '{user.role}' attempted to access department head route")
                return jsonify({
                    'success': False,
                    'message': 'Department head access required',
                    'user_role': user.role
                }), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Department head check failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': 'Authorization failed',
                'error': str(e)
            }), 500
            
    return decorated_function


def student_required(f):
    """
    Decorator to check if user is student
    
    Usage:
        @student_required
        def my_route():
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            
            if not user_id:
                logger.warning("No user identity found in JWT")
                return jsonify({'success': False, 'message': 'Authentication required'}), 401
            
            user = User.query.get(user_id)
            
            if not user:
                logger.warning(f"User {user_id} not found in database")
                return jsonify({'success': False, 'message': 'User not found'}), 404
            
            # user.role is already a string
            if user.role.lower() != 'student':
                logger.warning(f"User {user_id} with role '{user.role}' attempted to access student-only route")
                return jsonify({
                    'success': False,
                    'message': 'Student access required',
                    'user_role': user.role
                }), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Student check failed: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'message': 'Authorization failed',
                'error': str(e)
            }), 500
            
    return decorated_function


def module_owner_or_admin(f):
    """
    Decorator that checks if the current JWT user owns the module
    referenced by <module_id> in the URL, or is an admin.
    Must be placed AFTER @jwt_required().
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from app.module_processor.models import Module
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 404

            module_id = kwargs.get('module_id')
            if module_id is None:
                return jsonify({'success': False, 'message': 'Module ID required'}), 400

            module = Module.query.get(module_id)
            if not module:
                return jsonify({'success': False, 'message': 'Module not found'}), 404

            # Allow admin, department_head (for review), or the owning teacher
            allowed = (
                user.role.lower() in ('admin', 'department_head', 'department')
                or module.teacher_id == user_id
            )
            if not allowed:
                logger.warning(
                    f"IDOR blocked: user {user_id} (role={user.role}) "
                    f"tried to access module {module_id} owned by {module.teacher_id}"
                )
                return jsonify({'success': False, 'message': 'Unauthorized'}), 403

            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Module ownership check failed: {e}", exc_info=True)
            return jsonify({'success': False, 'message': 'Authorization failed'}), 500
    return decorated_function


def owner_or_admin_required(resource_user_id_field='user_id'):
    """
    Decorator to check if user is owner of resource or admin
    
    Args:
        resource_user_id_field: Name of the field containing the owner's user_id
    
    Usage:
        @owner_or_admin_required('creator_id')
        def my_route(resource_id):
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                user_id = get_jwt_identity()
                
                if not user_id:
                    logger.warning("No user identity found in JWT")
                    return jsonify({'success': False, 'message': 'Authentication required'}), 401
                
                user = User.query.get(user_id)
                
                if not user:
                    logger.warning(f"User {user_id} not found in database")
                    return jsonify({'success': False, 'message': 'User not found'}), 404
                
                # If admin, allow access
                if user.role.lower() == 'admin':
                    return f(*args, **kwargs)
                
                # Otherwise, check ownership in the route handler
                # The route handler should validate ownership
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Owner/admin check failed: {str(e)}", exc_info=True)
                return jsonify({
                    'success': False,
                    'message': 'Authorization failed',
                    'error': str(e)
                }), 500
                
        return decorated_function
    return decorator