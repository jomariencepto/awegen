# app/notifications/routes.py
import re
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.notifications.models import Notification
from app.database import db
from sqlalchemy import or_
from app.auth.models import User
from app.exam.models import Exam

notifications_bp = Blueprint('notifications', __name__)
DEPARTMENT_NOTIFICATION_ROLES = {'admin', 'department', 'department_head'}
EXAM_TITLE_PATTERN = re.compile(r'"([^"]+)"')


def _jwt_user_id_as_int():
    """Return JWT identity as int for DB lookups."""
    return int(get_jwt_identity())


def _extract_exam_title(message):
    if not message:
        return None

    match = EXAM_TITLE_PATTERN.search(str(message))
    if not match:
        return None

    title = str(match.group(1) or '').strip()
    return title or None


def _build_exam_query_for_user(current_user, exam_title):
    role = (current_user.role or '').lower()
    query = Exam.query.filter(Exam.title == exam_title)

    if role == 'teacher':
        return query.filter(Exam.teacher_id == current_user.user_id)

    if role in {'department', 'department_head'}:
        if not current_user.department_id:
            return None

        return query.join(User, Exam.teacher_id == User.user_id).filter(
            or_(
                Exam.department_id == current_user.department_id,
                User.department_id == current_user.department_id,
            )
        )

    if role == 'admin':
        return query

    return None


def _score_exam_for_notification(exam, message_lower):
    status = str(exam.admin_status or '').lower()
    score = 0

    if 'approved' in message_lower and status == 'approved':
        score += 6
    if 'revision' in message_lower and status == 'revision_required':
        score += 6
    if 'rejected' in message_lower and status == 'rejected':
        score += 6
    if 'for review' in message_lower and (status == 'pending' or bool(exam.sent_to_department)):
        score += 5
    if 'sent exam' in message_lower and bool(exam.sent_to_department):
        score += 3

    if bool(exam.sent_to_department):
        score += 1

    return score


def _resolve_notification_exam(current_user, notification):
    exam_title = _extract_exam_title(notification.text)
    if not exam_title:
        return None

    query = _build_exam_query_for_user(current_user, exam_title)
    if query is None:
        return None

    candidates = (
        query.order_by(
            Exam.updated_at.desc(),
            Exam.reviewed_at.desc(),
            Exam.created_at.desc(),
            Exam.exam_id.desc(),
        )
        .limit(25)
        .all()
    )
    if not candidates:
        return None

    message_lower = str(notification.text or '').lower()
    return max(
        candidates,
        key=lambda exam: (
            _score_exam_for_notification(exam, message_lower),
            exam.updated_at or exam.reviewed_at or exam.created_at,
            exam.exam_id,
        ),
    )


def _build_notification_target_path(current_user, exam, notification):
    if not exam:
        return None

    role = (current_user.role or '').lower()
    status = str(exam.admin_status or '').lower()
    message_lower = str(notification.text or '').lower()

    if role == 'teacher':
        if 'revision' in message_lower or 'rejected' in message_lower or status in {'revision_required', 'rejected'}:
            return f'/teacher/review-questions/{exam.exam_id}'
        if 'approved' in message_lower or status == 'approved':
            return f'/teacher/exam-preview/{exam.exam_id}'
        return f'/teacher/manage-exams'

    if role in {'department', 'department_head'}:
        if status == 'approved' and not exam.sent_to_department:
            return f'/department/exam-preview/{exam.exam_id}'
        if not exam.submitted_to_admin:
            return f'/department/review-questions/{exam.exam_id}'
        if status == 'pending' or bool(exam.sent_to_department):
            return f'/department/exam-review/{exam.exam_id}'
        return f'/department/exam-preview/{exam.exam_id}'

    if role == 'admin':
        return f'/admin/exams/{exam.exam_id}'

    return None


def _serialize_notification(notification, current_user):
    payload = notification.to_dict()
    if not current_user:
        return payload

    exam = _resolve_notification_exam(current_user, notification)
    if not exam:
        return payload

    payload['exam_id'] = exam.exam_id
    payload['exam_title'] = exam.title
    payload['target_path'] = _build_notification_target_path(current_user, exam, notification)
    return payload


@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications for the current user"""
    try:
        user_id = _jwt_user_id_as_int()
        current_user = User.query.get(user_id)
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
                'notifications': [
                    _serialize_notification(notification, current_user)
                    for notification in notifications.items
                ],
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
