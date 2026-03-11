from app.database import db
from app.users.models import Department, School, Subject
from app.users.schemas import DepartmentSchema, SchoolSchema, SubjectSchema, UserUpdateSchema, UserApprovalSchema
from app.auth.models import User
from app.utils.logger import get_logger
from sqlalchemy import asc

logger = get_logger(__name__)


class UserService:
    @staticmethod
    def get_all_users(page=1, per_page=10):
        try:
            users = User.query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'success': True,
                'users': [user.to_dict() for user in users.items],
                'total': users.total,
                'pages': users.pages,
                'current_page': users.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting users: {str(e)}")
            return {'success': False, 'message': 'Failed to get users'}, 500
    
    @staticmethod
    def get_user_by_id(user_id):
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}, 404
            
            return {
                'success': True,
                'user': user.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return {'success': False, 'message': 'Failed to get user'}, 500
    
    @staticmethod
    def update_user(user_id, user_data):
        try:
            schema = UserUpdateSchema()
            validated_data = schema.load(user_data)
            
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}, 404
            
            # Update user fields
            for field, value in validated_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)

            # Keep denormalized department_name in sync with department_id.
            if 'department_id' in validated_data:
                if user.department_id:
                    department = Department.query.get(user.department_id)
                    user.department_name = department.department_name if department else None
                else:
                    user.department_name = None
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'User updated successfully',
                'user': user.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update user'}, 500
    
    @staticmethod
    def approve_user(approval_data):
        try:
            schema = UserApprovalSchema()
            validated_data = schema.load(approval_data)
            
            user = User.query.get(validated_data['user_id'])
            if not user:
                return {'success': False, 'message': 'User not found'}, 404
            
            requested_approval = bool(validated_data['is_approved'])
            was_approved = bool(user.is_approved)
            user.is_approved = requested_approval
            db.session.commit()

            email_notification_sent = None
            if requested_approval and not was_approved and user.email:
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
                            f"Account approved for user_id={user.user_id}, "
                            f"but approval email was not sent (email service not configured or failed)."
                        )
                except Exception as email_error:
                    email_notification_sent = False
                    logger.error(
                        f"Account approved for user_id={user.user_id}, "
                        f"but failed to send approval email: {str(email_error)}"
                    )
             
            response = {
                'success': True,
                'message': 'User approval status updated successfully',
                'user': user.to_dict()
            }
            if email_notification_sent is not None:
                response['email_notification_sent'] = email_notification_sent

            return response, 200
             
        except Exception as e:
            logger.error(f"Error approving user: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update user approval'}, 500
    
    @staticmethod
    def get_all_departments():
        try:
            departments = Department.query.all()
            return {
                'success': True,
                'departments': [dept.to_dict() for dept in departments]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting departments: {str(e)}")
            return {'success': False, 'message': 'Failed to get departments'}, 500
    
    @staticmethod
    def get_all_schools():
        try:
            schools = School.query.all()
            return {
                'success': True,
                'schools': [school.to_dict() for school in schools]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting schools: {str(e)}")
            return {'success': False, 'message': 'Failed to get schools'}, 500
    
    @staticmethod
    def get_subjects_by_department(department_id):
        try:
            subjects = Subject.query.filter_by(department_id=department_id).all()
            return {
                'success': True,
                'subjects': [subject.to_dict() for subject in subjects]
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting subjects: {str(e)}")
            return {'success': False, 'message': 'Failed to get subjects'}, 500

    @staticmethod
    def get_all_subjects():
        try:
            subjects = (
                Subject.query
                .join(Department, Subject.department_id == Department.department_id)
                .order_by(asc(Department.department_name), asc(Subject.subject_name))
                .all()
            )

            subject_list = []
            for subject in subjects:
                subject_data = subject.to_dict()
                subject_data['department_name'] = (
                    subject.department.department_name if subject.department else None
                )
                subject_list.append(subject_data)

            return {
                'success': True,
                'subjects': subject_list
            }, 200

        except Exception as e:
            logger.error(f"Error getting all subjects: {str(e)}")
            return {'success': False, 'message': 'Failed to get all subjects'}, 500
