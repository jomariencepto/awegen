from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.approval.workflow import ApprovalWorkflow
from app.utils.decorators import role_required

approval_bp = Blueprint('approvals', __name__)


@approval_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = get_jwt_identity()
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    result, status_code = ApprovalWorkflow.get_user_notifications(user_id, unread_only)
    return jsonify(result), status_code


@approval_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    result, status_code = ApprovalWorkflow.mark_notification_read(notification_id)
    return jsonify(result), status_code


@approval_bp.route('/notifications/read-all', methods=['POST'])
@jwt_required()
def mark_all_notifications_read():
    user_id = get_jwt_identity()
    result, status_code = ApprovalWorkflow.mark_all_notifications_read(user_id)
    return jsonify(result), status_code


@approval_bp.route('/teacher-approvals', methods=['GET'])
@jwt_required()
@role_required(['admin', 'department', 'department_head'])
def get_teacher_approvals():
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = ApprovalWorkflow.get_teacher_approvals(status, page, per_page)
    return jsonify(result), status_code


@approval_bp.route('/teacher-approvals/<int:approval_id>', methods=['PUT'])
@jwt_required()
@role_required(['admin', 'department', 'department_head'])
def update_teacher_approval(approval_id):
    data = request.get_json()
    approver_id = get_jwt_identity()
    
    result, status_code = ApprovalWorkflow.update_teacher_approval(approval_id, data, approver_id)
    return jsonify(result), status_code


@approval_bp.route('/user/<int:user_id>/approvals', methods=['GET'])
@jwt_required()
def get_user_approvals(user_id):
    current_user_id = int(get_jwt_identity())
    
    # Users can only view their own approvals unless they're admin
    from app.auth.models import User
    current_user = User.query.get(current_user_id)
    
    current_role = (current_user.role or '').lower() if current_user else ''
    if current_user_id != user_id and current_role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    status = request.args.get('status')
    result, status_code = ApprovalWorkflow.get_user_approvals(user_id, status)
    return jsonify(result), status_code
