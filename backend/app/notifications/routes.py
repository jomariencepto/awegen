# app/notifications/routes.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.notifications.models import Notification
from app.database import db

notifications_bp = Blueprint('notifications', __name__)
DEPARTMENT_NOTIFICATION_ROLES = {'admin', 'department', 'department_head'}


def _jwt_user_id_as_int():
    """Return JWT identity as int for DB lookups."""
    return int(get_jwt_identity())


@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications for the current user"""
    try:
        user_id = _jwt_user_id_as_int()
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Filter by type if provided
        notification_type = request.args.get('type')
        
        # Query notifications for the user
        query = Notification.query.filter_by(user_id=user_id)
        if notification_type:
            query = query.filter_by(type=notification_type)
            
        notifications = query.order_by(Notification.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Format the response
        return jsonify({
            'success': True,
            'message': 'Notifications retrieved successfully',
            'data': {
                'notifications': [notification.to_dict() for notification in notifications.items],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': notifications.total,
                    'pages': notifications.pages
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@notifications_bp.route('/teacher/<int:teacher_id>', methods=['GET'])
@jwt_required()
def get_teacher_notifications(teacher_id):
    """Get notifications for a specific teacher"""
    try:
        current_user_id = _jwt_user_id_as_int()
        
        # Verify the requesting user is either the teacher or an admin
        if str(current_user_id) != str(teacher_id):
            from app.auth.models import User
            current_user = User.query.get(current_user_id)
            current_role = (current_user.role or '').lower() if current_user else ''
            if current_role not in DEPARTMENT_NOTIFICATION_ROLES:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized to view these notifications'
                }), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Filter by type if provided
        notification_type = request.args.get('type')
        
        # Query notifications for the teacher
        query = Notification.query.filter_by(user_id=teacher_id)
        if notification_type:
            query = query.filter_by(type=notification_type)
            
        notifications = query.order_by(Notification.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Format the response
        return jsonify({
            'success': True,
            'message': 'Notifications retrieved successfully',
            'data': {
                'notifications': [notification.to_dict() for notification in notifications.items],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': notifications.total,
                    'pages': notifications.pages
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@notifications_bp.route('/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        user_id = _jwt_user_id_as_int()
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        
        if not notification:
            return jsonify({
                'success': False,
                'message': 'Notification not found'
            }), 404
        
        notification.read = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Notification marked as read',
            'data': {'id': notification_id}
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@notifications_bp.route('/unread/count', methods=['GET'])
@jwt_required()
def get_unread_count():
    """Get unread notification count for current user"""
    try:
        user_id = _jwt_user_id_as_int()
        unread_count = Notification.query.filter_by(user_id=user_id, read=False).count()
        
        return jsonify({
            'success': True,
            'message': 'Unread count retrieved successfully',
            'data': {'unread_count': unread_count}
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@notifications_bp.route('/teacher/<int:teacher_id>/unread/count', methods=['GET'])
@jwt_required()
def get_teacher_unread_count(teacher_id):
    """Get unread notification count for a specific teacher"""
    try:
        current_user_id = _jwt_user_id_as_int()
        
        # Verify the requesting user is either the teacher or an admin
        if str(current_user_id) != str(teacher_id):
            from app.auth.models import User
            current_user = User.query.get(current_user_id)
            current_role = (current_user.role or '').lower() if current_user else ''
            if current_role not in DEPARTMENT_NOTIFICATION_ROLES:
                return jsonify({
                    'success': False,
                    'message': 'Unauthorized to view this information'
                }), 403
        
        unread_count = Notification.query.filter_by(user_id=teacher_id, read=False).count()
        
        return jsonify({
            'success': True,
            'message': 'Unread count retrieved successfully',
            'data': {'unread_count': unread_count}
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@notifications_bp.route('/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_read():
    """Mark all notifications as read for the current user"""
    try:
        user_id = _jwt_user_id_as_int()
        
        # Update all unread notifications
        Notification.query.filter_by(user_id=user_id, read=False).update({'read': True})
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'All notifications marked as read'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
