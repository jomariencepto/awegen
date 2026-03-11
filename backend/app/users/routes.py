from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.users.service import UserService
from app.utils.decorators import role_required
from app.database import db  # Added for database transactions

users_bp = Blueprint('users', __name__)

# ===================== USERS =====================


@users_bp.route('/', methods=['GET'])
@jwt_required()
@role_required(['admin', 'department'])
def get_all_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = UserService.get_all_users(page, per_page)
    return jsonify(result), status_code


@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    current_user_id = get_jwt_identity()

    from app.auth.models import User
    current_user = User.query.get(current_user_id)

    if current_user_id != user_id and current_user.role not in ['admin', 'department']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    result, status_code = UserService.get_user_by_id(user_id)
    return jsonify(result), status_code


@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = get_jwt_identity()

    from app.auth.models import User
    current_user = User.query.get(current_user_id)

    # Allow admins and department roles to update other users
    if current_user_id != user_id and current_user.role not in ['admin', 'department']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    result, status_code = UserService.update_user(user_id, data)
    return jsonify(result), status_code


@users_bp.route('/approve', methods=['POST'])
@jwt_required()
@role_required(['admin', 'department'])
def approve_user():
    data = request.get_json()
    result, status_code = UserService.approve_user(data)
    return jsonify(result), status_code


# ===================== PROFILE & SETTINGS ENDPOINTS =====================
# These endpoints are used by the Settings page

@users_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get the currently logged-in user's details
    Used by Settings.jsx to populate form
    """
    user_id = get_jwt_identity()
    
    from app.auth.models import User
    # Ensure user_id is an integer if it comes from string token
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid user ID in token'}), 400

    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # FIX: Access user.user_id instead of user.id
    # FIX: Access user.role (String) instead of user.role.role_name
    return jsonify({
        'success': True,
        'user': {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role, 
            'user_id': user.user_id
        }
    }), 200


@users_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_current_user():
    """
    Update the currently logged-in user's profile
    Used by Settings.jsx to save name changes
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Use UserService if it handles generic updates, or manual update here
    # Assuming we are updating first_name and last_name
    
    from app.auth.models import User
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Profile updated successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': 'Failed to update profile'
        }), 500


@users_bp.route('/change-password', methods=['PUT'])
@jwt_required()
def change_password():
    """
    Update the currently logged-in user's password
    Used by Settings.jsx security tab
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not current_password or not new_password:
        return jsonify({
            'success': False, 
            'message': 'Current password and new password are required'
        }), 400
    
    from app.auth.models import User
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Verify current password
    # Note: This assumes User model has check_password method
    if not user.check_password(current_password):
        return jsonify({
            'success': False, 
            'message': 'Current password is incorrect'
        }), 400
    
    # Set new password (hashing is handled inside set_password)
    user.set_password(new_password)
    
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Password changed successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': 'Failed to change password'
        }), 500


# ===================== PUBLIC LOOKUPS =====================
# These endpoints are PUBLIC and used during registration
# DO NOT add @jwt_required() to these endpoints


@users_bp.route('/departments', methods=['GET'])
def get_departments():
    """
    PUBLIC: Used during registration
    Get all departments
    """
    result, status_code = UserService.get_all_departments()
    return jsonify(result), status_code


@users_bp.route('/schools', methods=['GET'])
def get_schools():
    """
    PUBLIC: Used during registration
    Get all schools
    """
    result, status_code = UserService.get_all_schools()
    return jsonify(result), status_code


@users_bp.route('/subjects/<int:department_id>', methods=['GET'])
def get_subjects_by_department(department_id):
    """
    PUBLIC: Used during registration
    Get subjects for a specific department
    REMOVED @jwt_required() to allow access during registration
    """
    result, status_code = UserService.get_subjects_by_department(department_id)
    return jsonify(result), status_code


@users_bp.route('/subjects', methods=['GET'])
def get_all_subjects():
    """
    PUBLIC: Used by upload module pages
    Get all subjects across all departments
    """
    result, status_code = UserService.get_all_subjects()
    return jsonify(result), status_code
