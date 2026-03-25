from app.database import db
from app.users.models import Department, School, Subject, TeacherSubjectAssignment
from app.users.schemas import (
    CurrentUserProfileUpdateSchema,
    DepartmentSchema,
    SchoolSchema,
    SubjectSchema,
    UserUpdateSchema,
    UserApprovalSchema,
)
from app.auth.models import User
from app.auth.service import AuthService
from app.utils.logger import get_logger
from sqlalchemy import asc
from sqlalchemy import func
from marshmallow import ValidationError

logger = get_logger(__name__)


class UserService:
    @staticmethod
    def _ensure_teacher_subject_assignments_table():
        """Create the additive teacher_subject_assignments table for older databases."""
        try:
            TeacherSubjectAssignment.__table__.create(bind=db.engine, checkfirst=True)
            return True
        except Exception as exc:
            logger.error(f"Failed to ensure teacher_subject_assignments table exists: {exc}")
            return False

    @staticmethod
    def _serialize_subject(subject):
        subject_data = subject.to_dict()
        subject_data['department_name'] = (
            subject.department.department_name if getattr(subject, 'department', None) else None
        )
        return subject_data

    @staticmethod
    def get_teacher_assigned_subject_ids(teacher_id, ensure_table=True):
        if ensure_table and not UserService._ensure_teacher_subject_assignments_table():
            return None

        rows = (
            TeacherSubjectAssignment.query
            .filter_by(teacher_id=teacher_id)
            .all()
        )
        return {int(row.subject_id) for row in rows if row.subject_id is not None}

    @staticmethod
    def prune_teacher_subject_assignments_for_department(teacher_id, department_id):
        # Teacher subject assignments are now managed independently from the teacher department.
        return True

    @staticmethod
    def get_current_user_subjects(user_id):
        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}, 404

            current_role = (user.role or '').strip().lower()
            response_department_id = user.department_id
            response_department_name = user.department_name
            subjects = []

            if current_role == 'teacher':
                if not UserService._ensure_teacher_subject_assignments_table():
                    return {
                        'success': False,
                        'message': 'Failed to load teacher subject assignments'
                    }, 500

                assigned_subject_ids = UserService.get_teacher_assigned_subject_ids(
                    user.user_id,
                    ensure_table=False,
                ) or set()

                if assigned_subject_ids:
                    subject_rows = (
                        Subject.query
                        .join(Department, Subject.department_id == Department.department_id)
                        .filter(Subject.subject_id.in_(assigned_subject_ids))
                        .order_by(asc(Department.department_name), asc(Subject.subject_name))
                        .all()
                    )
                    subjects = [UserService._serialize_subject(subject) for subject in subject_rows]

                if not response_department_name and user.department:
                    response_department_name = user.department.department_name

                return {
                    'success': True,
                    'subjects': subjects,
                    'assigned_subject_ids': sorted(assigned_subject_ids),
                    'department_id': response_department_id,
                    'department_name': response_department_name,
                    'assignment_required': True,
                }, 200

            if user.department_id:
                subject_rows = (
                    Subject.query
                    .join(Department, Subject.department_id == Department.department_id)
                    .filter(Subject.department_id == user.department_id)
                    .order_by(asc(Subject.subject_name))
                    .all()
                )
                subjects = [UserService._serialize_subject(subject) for subject in subject_rows]

                if not response_department_name and user.department:
                    response_department_name = user.department.department_name
            else:
                subject_rows = (
                    Subject.query
                    .join(Department, Subject.department_id == Department.department_id)
                    .order_by(asc(Department.department_name), asc(Subject.subject_name))
                    .all()
                )
                subjects = [UserService._serialize_subject(subject) for subject in subject_rows]

            return {
                'success': True,
                'subjects': subjects,
                'department_id': response_department_id,
                'department_name': response_department_name,
                'assignment_required': False,
            }, 200

        except Exception as e:
            logger.error(f"Error getting current user subjects: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get subjects'}, 500

    @staticmethod
    def update_current_user_profile(user_id, profile_data):
        try:
            schema = CurrentUserProfileUpdateSchema()
            validated_data = schema.load(profile_data or {})
        except ValidationError as err:
            first_error = next(iter(err.messages.values()), ['Invalid input'])
            message = first_error[0] if isinstance(first_error, list) and first_error else 'Invalid input'
            return {'success': False, 'message': message, 'errors': err.messages}, 400

        try:
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'message': 'User not found'}, 404

            first_name = (validated_data.get('first_name') or '').strip()
            last_name = (validated_data.get('last_name') or '').strip()
            new_email = (validated_data.get('email') or '').strip().lower()
            current_password = validated_data.get('current_password') or ''

            if not first_name or not AuthService.NAME_PATTERN.match(first_name):
                return {'success': False, 'message': 'First name must contain letters only'}, 400

            if not last_name or not AuthService.NAME_PATTERN.match(last_name):
                return {'success': False, 'message': 'Last name must contain letters only'}, 400

            email_changed = new_email != (user.email or '').strip().lower()
            if email_changed and not current_password:
                return {
                    'success': False,
                    'message': 'Current password is required to change your email'
                }, 400

            if email_changed and not user.check_password(current_password):
                return {
                    'success': False,
                    'message': 'Current password is incorrect'
                }, 400

            if email_changed:
                existing_user = (
                    User.query
                    .filter(func.lower(User.email) == new_email, User.user_id != user.user_id)
                    .first()
                )
                if existing_user:
                    return {'success': False, 'message': 'Email already registered'}, 409

            user.first_name = first_name
            user.last_name = last_name
            if email_changed:
                user.email = new_email

            db.session.commit()

            email_notification_sent = None
            if email_changed:
                try:
                    from app.utils.email_service import send_email_change_confirmation_email

                    email_notification_sent = bool(
                        send_email_change_confirmation_email(
                            to_email=new_email,
                            full_name=f"{first_name} {last_name}".strip() or new_email,
                            role_name=user.role,
                        )
                    )
                except Exception as exc:
                    logger.error(f"Failed to send email change confirmation: {exc}", exc_info=True)
                    email_notification_sent = False

            response = {
                'success': True,
                'message': 'Profile updated successfully',
                'user': user.to_dict(),
            }
            if email_changed:
                response['email_changed'] = True
                response['email_notification_sent'] = bool(email_notification_sent)
                if email_notification_sent:
                    response['message'] = (
                        'Profile updated successfully. A confirmation email was sent to your new address.'
                    )
                else:
                    response['message'] = (
                        'Profile updated successfully, but we could not send a confirmation email to your new address.'
                    )
            else:
                response['email_changed'] = False

            return response, 200
        except Exception as e:
            logger.error(f"Error updating current user profile: {str(e)}", exc_info=True)
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update profile'}, 500

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
                subject_list.append(UserService._serialize_subject(subject))

            return {
                'success': True,
                'subjects': subject_list
            }, 200

        except Exception as e:
            logger.error(f"Error getting all subjects: {str(e)}")
            return {'success': False, 'message': 'Failed to get all subjects'}, 500
