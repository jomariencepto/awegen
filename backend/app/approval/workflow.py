from app.database import db
from app.notifications.models import Notification  # Changed import location
from app.approval.models import TeacherApproval
from app.approval.schemas import NotificationCreateSchema, TeacherApprovalCreateSchema, TeacherApprovalUpdateSchema
from app.utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)


class ApprovalWorkflow:
    @staticmethod
    def create_notification(user_id, message, type):
        """Create a notification for a user"""
        try:
            notification = Notification(
                user_id=user_id,
                type=type,
                text=message
            )
            db.session.add(notification)
            db.session.commit()
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def get_user_notifications(user_id, unread_only=False):
        """Get notifications for a user"""
        try:
            query = Notification.query.filter_by(user_id=user_id)
            
            if unread_only:
                query = query.filter_by(read=False)
            
            notifications = query.order_by(Notification.created_at.desc()).all()
            
            return {
                'success': True,
                'notifications': [notification.to_dict() for notification in notifications]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting notifications: {str(e)}")
            return {'success': False, 'message': 'Failed to get notifications'}, 500
    
    @staticmethod
    def mark_notification_read(notification_id):
        """Mark a notification as read"""
        try:
            notification = Notification.query.get(notification_id)
            if not notification:
                return {'success': False, 'message': 'Notification not found'}, 404
            
            notification.read = True
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Notification marked as read',
                'notification': notification.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to mark notification as read'}, 500
    
    @staticmethod
    def mark_all_notifications_read(user_id):
        """Mark all notifications for a user as read"""
        try:
            notifications = Notification.query.filter_by(user_id=user_id, read=False).all()
            
            for notification in notifications:
                notification.read = True
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Marked {len(notifications)} notifications as read'
            }, 200
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to mark notifications as read'}, 500
    
    @staticmethod
    def create_teacher_approval(user_id, department_name):
        """Create a teacher approval request"""
        try:
            approval = TeacherApproval(
                user_id=user_id,
                department_name=department_name,
                status='pending'
            )
            db.session.add(approval)
            db.session.commit()
            
            # Create notification for department head
            from app.users.models import Department
            department = Department.query.filter_by(department_name=department_name).first()
            
            if department:
                # Find department head users
                from app.auth.models import User, Role
                department_role = Role.query.filter_by(role_name='department').first()
                
                if department_role:
                    department_heads = User.query.filter_by(
                        role_id=department_role.role_id,
                        department_id=department.department_id
                    ).all()
                    
                    for head in department_heads:
                        ApprovalWorkflow.create_notification(
                            user_id=head.user_id,
                            message=f"New teacher approval request for {department_name}",
                            type='teacher_approval'
                        )
            
            return approval
            
        except Exception as e:
            logger.error(f"Error creating teacher approval: {str(e)}")
            db.session.rollback()
            return None
    
    @staticmethod
    def get_teacher_approvals(status=None, page=1, per_page=10):
        """Get teacher approvals with optional status filter"""
        try:
            query = TeacherApproval.query
            
            if status:
                query = query.filter_by(status=status)
            
            approvals = query.order_by(TeacherApproval.created_at.desc()).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'success': True,
                'approvals': [approval.to_dict() for approval in approvals.items],
                'total': approvals.total,
                'pages': approvals.pages,
                'current_page': approvals.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting teacher approvals: {str(e)}")
            return {'success': False, 'message': 'Failed to get teacher approvals'}, 500
    
    @staticmethod
    def update_teacher_approval(approval_id, approval_data, approver_id):
        """Update teacher approval status"""
        try:
            schema = TeacherApprovalUpdateSchema()
            validated_data = schema.load(approval_data)
            
            approval = TeacherApproval.query.get(approval_id)
            if not approval:
                return {'success': False, 'message': 'Approval not found'}, 404

            from app.auth.models import User
            user = User.query.get(approval.user_id)
            if not user:
                return {'success': False, 'message': 'Approved user record not found'}, 404
             
            # Update approval
            approval.status = validated_data['status']
            approval.approved_by = approver_id
            approval.updated_at = datetime.utcnow()
            
            if validated_data['status'] == 'rejected':
                approval.rejection_reason = validated_data['rejection_reason']

            # Keep auth gate in sync with approval decision.
            user.is_approved = validated_data['status'] == 'approved'
             
            db.session.commit()

            email_notification_sent = None
            if validated_data['status'] == 'approved' and user.email:
                try:
                    from app.utils.email_service import send_account_approval_email
                    full_name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
                    if not full_name:
                        full_name = user.email
                    email_notification_sent = bool(
                        send_account_approval_email(
                            to_email=user.email,
                            full_name=full_name,
                            role_name=user.role
                        )
                    )
                    if not email_notification_sent:
                        logger.warning(
                            f"Teacher approval updated to approved for user_id={user.user_id}, "
                            f"but approval email was not sent."
                        )
                except Exception as email_error:
                    email_notification_sent = False
                    logger.error(
                        f"Teacher approval updated to approved for user_id={user.user_id}, "
                        f"but failed to send approval email: {str(email_error)}"
                    )
             
            # Create notification for teacher
            ApprovalWorkflow.create_notification(
                user_id=approval.user_id,
                message=f"Your teacher approval has been {validated_data['status']}",
                type='teacher_approval_response'
            )
            
            response = {
                'success': True,
                'message': f'Teacher approval {validated_data["status"]} successfully',
                'approval': approval.to_dict()
            }
            if email_notification_sent is not None:
                response['email_notification_sent'] = email_notification_sent

            return response, 200
             
        except Exception as e:
            logger.error(f"Error updating teacher approval: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update teacher approval'}, 500
    
    @staticmethod
    def get_user_approvals(user_id, status=None):
        """Get approvals for a specific user"""
        try:
            query = TeacherApproval.query.filter_by(user_id=user_id)
            
            if status:
                query = query.filter_by(status=status)
            
            approvals = query.order_by(TeacherApproval.created_at.desc()).all()
            
            return {
                'success': True,
                'approvals': [approval.to_dict() for approval in approvals]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting user approvals: {str(e)}")
            return {'success': False, 'message': 'Failed to get user approvals'}, 500
