from app.database import db
from app.auth.models import User, Role
from app.auth.service import AuthService
from app.admin.schemas import AdminCreateUserSchema, AdminAssignTeacherSubjectsSchema
from app.users.models import Department, School, Subject, TeacherSubjectAssignment
from app.users.service import UserService
from app.exam.models import Exam, ExamCategory
from app.notifications.models import Notification
from app.utils.logger import get_logger
from app.utils.exam_password import get_exam_download_password, set_exam_download_password
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
from werkzeug.security import generate_password_hash

logger = get_logger(__name__)


class AdminService:
    @staticmethod
    def _managed_role_label(requested_role, fallback_role_name=None):
        normalized = str(requested_role or fallback_role_name or '').strip().lower()
        if normalized in {'department_head', 'department'}:
            return 'Department Head'
        return 'Teacher'

    @staticmethod
    def _build_account_created_notification_message(
        role_label,
        department_name='',
        is_active=True,
        is_approved=True,
    ):
        department_suffix = f" for {department_name}" if department_name else ""

        if not is_active:
            return (
                f"Your {role_label} account{department_suffix} was created by admin. "
                "It is currently inactive. Please wait for activation before signing in."
            )

        if not is_approved:
            return (
                f"Your {role_label} account{department_suffix} was created by admin. "
                "It is waiting for department approval before you can sign in."
            )

        return (
            f"Your {role_label} account{department_suffix} was created by admin. "
            "You can now sign in using your registered email."
        )

    @staticmethod
    def _resolve_managed_role(requested_role):
        """Resolve UI role labels to the actual role row stored in the database."""
        normalized_role = str(requested_role or '').strip().lower()
        role_candidates = {
            'teacher': ['teacher'],
            'department_head': ['department_head', 'department'],
        }

        for role_name in role_candidates.get(normalized_role, []):
            role = Role.query.filter(func.lower(Role.role_name) == role_name.lower()).first()
            if role:
                return role

        return None

    @staticmethod
    def get_all_users(page=1, per_page=10, search=''):
        """Get all users with pagination"""
        try:
            normalized_search = (search or '').strip().lower()
            query = User.query

            if normalized_search:
                search_pattern = f"%{normalized_search}%"
                query = query.filter(
                    or_(
                        func.lower(
                            func.trim(
                                func.coalesce(User.first_name, '') + ' ' + func.coalesce(User.last_name, '')
                            )
                        ).like(search_pattern),
                        func.lower(func.coalesce(User.first_name, '')).like(search_pattern),
                        func.lower(func.coalesce(User.last_name, '')).like(search_pattern),
                        func.lower(func.coalesce(User.username, '')).like(search_pattern),
                        func.lower(func.coalesce(User.email, '')).like(search_pattern),
                        func.lower(func.coalesce(User.role, '')).like(search_pattern),
                        func.lower(func.coalesce(User.department_name, '')).like(search_pattern),
                    )
                )

            users = (
                query
                .order_by(User.created_at.desc(), User.user_id.desc())
                .paginate(
                page=page,
                per_page=per_page,
                error_out=False
                )
            )
            
            return {
                'success': True,
                'users': [user.to_dict() for user in users.items],
                'total': users.total,
                'pages': users.pages,
                'current_page': users.page,
                'search': normalized_search,
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            return {'success': False, 'message': 'Failed to get users'}, 500

    @staticmethod
    def get_teacher_subject_assignments(teacher_id):
        try:
            if not UserService._ensure_teacher_subject_assignments_table():
                return {
                    'success': False,
                    'message': 'Failed to load teacher subject assignments'
                }, 500

            teacher = User.query.get(teacher_id)
            if not teacher:
                return {'success': False, 'message': 'Teacher not found'}, 404

            if (teacher.role or '').strip().lower() != 'teacher':
                return {'success': False, 'message': 'Selected user is not a teacher'}, 400

            department = Department.query.get(teacher.department_id)
            available_subject_rows = (
                Subject.query
                .join(Department, Subject.department_id == Department.department_id)
                .order_by(Department.department_name.asc(), Subject.subject_name.asc())
                .all()
            )
            assigned_subject_ids = UserService.get_teacher_assigned_subject_ids(
                teacher.user_id,
                ensure_table=False,
            ) or set()

            available_subjects = []
            for subject in available_subject_rows:
                subject_data = subject.to_dict()
                subject_department = subject.department
                subject_data['department_name'] = (
                    subject_department.department_name if subject_department else None
                )
                available_subjects.append(subject_data)

            return {
                'success': True,
                'teacher': teacher.to_dict(),
                'available_subjects': available_subjects,
                'assigned_subject_ids': sorted(assigned_subject_ids),
                'department_id': teacher.department_id,
                'department_name': (
                    department.department_name if department else teacher.department_name
                ),
            }, 200

        except Exception as e:
            logger.error(f"Error getting teacher subject assignments: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get teacher subjects'}, 500

    @staticmethod
    def update_teacher_subject_assignments(teacher_id, assignment_data, assigned_by=None):
        try:
            schema = AdminAssignTeacherSubjectsSchema()
            validated_data = schema.load(assignment_data or {})
        except ValidationError as err:
            first_error = next(iter(err.messages.values()), ['Invalid input'])
            message = first_error[0] if isinstance(first_error, list) and first_error else 'Invalid input'
            return {'success': False, 'message': message, 'errors': err.messages}, 400

        try:
            if not UserService._ensure_teacher_subject_assignments_table():
                return {
                    'success': False,
                    'message': 'Failed to save teacher subject assignments'
                }, 500

            teacher = User.query.get(teacher_id)
            if not teacher:
                return {'success': False, 'message': 'Teacher not found'}, 404

            if (teacher.role or '').strip().lower() != 'teacher':
                return {'success': False, 'message': 'Selected user is not a teacher'}, 400

            requested_subject_ids = sorted({
                int(subject_id)
                for subject_id in (validated_data.get('subject_ids') or [])
                if subject_id is not None
            })

            valid_subjects = []
            if requested_subject_ids:
                valid_subjects = Subject.query.filter(
                    Subject.subject_id.in_(requested_subject_ids)
                ).all()

                if len(valid_subjects) != len(requested_subject_ids):
                    found_ids = {int(subject.subject_id) for subject in valid_subjects}
                    missing_ids = sorted(set(requested_subject_ids) - found_ids)
                    return {
                        'success': False,
                        'message': f'One or more subjects were not found: {", ".join(map(str, missing_ids))}'
                    }, 404

            TeacherSubjectAssignment.query.filter_by(
                teacher_id=teacher.user_id
            ).delete(synchronize_session=False)

            for subject_id in requested_subject_ids:
                db.session.add(
                    TeacherSubjectAssignment(
                        teacher_id=teacher.user_id,
                        subject_id=subject_id,
                        assigned_by=assigned_by,
                    )
                )

            db.session.commit()

            result, status_code = AdminService.get_teacher_subject_assignments(teacher_id)
            if status_code != 200:
                return result, status_code

            result['message'] = (
                'Teacher subjects updated successfully'
                if requested_subject_ids else
                'Teacher subjects cleared successfully'
            )
            return result, 200

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating teacher subject assignments: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to update teacher subjects'}, 500

    @staticmethod
    def create_user_account(user_data, created_by=None):
        """Create a teacher or department-head account from the admin panel."""
        try:
            schema = AdminCreateUserSchema()
            validated_data = schema.load(user_data or {})
        except ValidationError as err:
            first_error = next(iter(err.messages.values()), ['Invalid input'])
            message = first_error[0] if isinstance(first_error, list) and first_error else 'Invalid input'
            return {'success': False, 'message': message, 'errors': err.messages}, 400

        try:
            email = (validated_data.get('email') or '').strip().lower()
            first_name = (validated_data.get('first_name') or '').strip()
            last_name = (validated_data.get('last_name') or '').strip()
            password = validated_data.get('password') or ''
            requested_role = validated_data.get('role')
            school_id_number = int(validated_data.get('school_id_number'))
            department_id = int(validated_data.get('department_id'))
            requested_subject_ids = sorted({
                int(subject_id)
                for subject_id in (validated_data.get('subject_ids') or [])
                if subject_id is not None
            })
            requested_active = bool(validated_data.get('is_active', True))

            if not first_name or not AuthService.NAME_PATTERN.match(first_name):
                return {'success': False, 'message': 'First name must contain letters only'}, 400

            if not last_name or not AuthService.NAME_PATTERN.match(last_name):
                return {'success': False, 'message': 'Last name must contain letters only'}, 400

            is_valid_password, password_error = AuthService.validate_strong_password(password)
            if not is_valid_password:
                return {'success': False, 'message': password_error}, 400

            role = AdminService._resolve_managed_role(requested_role)
            if not role:
                return {'success': False, 'message': 'Selected role is not available in the database'}, 400

            is_teacher_account = (role.role_name or '').strip().lower() == 'teacher'
            requires_department_approval = is_teacher_account and not requested_active
            account_is_active = True if requires_department_approval else requested_active
            account_is_approved = not requires_department_approval

            school = School.query.get(school_id_number)
            if not school:
                return {'success': False, 'message': 'School not found'}, 404

            department = Department.query.get(department_id)
            if not department:
                return {'success': False, 'message': 'Department not found'}, 404

            if department.school_id_number != school_id_number:
                return {
                    'success': False,
                    'message': 'Selected department does not belong to the selected school',
                }, 400

            valid_subjects = []
            if is_teacher_account:
                if not requested_subject_ids:
                    return {
                        'success': False,
                        'message': 'Please assign at least one subject for this teacher',
                    }, 400

                valid_subjects = (
                    Subject.query
                    .filter(Subject.subject_id.in_(requested_subject_ids))
                    .all()
                )
                if len(valid_subjects) != len(requested_subject_ids):
                    found_ids = {subject.subject_id for subject in valid_subjects}
                    missing_ids = sorted(set(requested_subject_ids) - found_ids)
                    return {
                        'success': False,
                        'message': f'Invalid subject selection: {", ".join(map(str, missing_ids))}',
                    }, 400

            AuthService._purge_expired_unverified_registration(email=email)

            existing_user = User.query.filter(func.lower(User.email) == email).first()
            if existing_user:
                return {'success': False, 'message': 'Email already registered'}, 409

            username = AuthService.generate_username(email)
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1

            new_user = User(
                email=email,
                password_hash=generate_password_hash(password),
                first_name=first_name,
                last_name=last_name,
                username=username,
                role=role.role_name,
                role_id=role.role_id,
                school_id_number=school_id_number,
                department_id=department.department_id,
                department_name=department.department_name,
                is_verified=True,
                is_approved=account_is_approved,
                is_active=account_is_active,
            )

            db.session.add(new_user)
            db.session.flush()

            if is_teacher_account:
                if not UserService._ensure_teacher_subject_assignments_table():
                    db.session.rollback()
                    return {'success': False, 'message': 'Failed to save teacher subjects'}, 500

                for subject_id in requested_subject_ids:
                    db.session.add(TeacherSubjectAssignment(
                        teacher_id=new_user.user_id,
                        subject_id=subject_id,
                        assigned_by=created_by,
                    ))

            created_role_label = AdminService._managed_role_label(requested_role, role.role_name)
            db.session.add(Notification(
                user_id=new_user.user_id,
                type='account_created',
                text=AdminService._build_account_created_notification_message(
                    role_label=created_role_label,
                    department_name=department.department_name,
                    is_active=account_is_active,
                    is_approved=account_is_approved,
                )
            ))

            db.session.commit()

            if is_teacher_account and requires_department_approval:
                message = (
                    f'{created_role_label} account created successfully with {len(requested_subject_ids)} '
                    f'assigned subject(s). Department approval is required before the teacher can log in.'
                )
            elif is_teacher_account:
                message = (
                    f'{created_role_label} account created successfully with {len(requested_subject_ids)} '
                    f'assigned subject(s)'
                )
            elif not requested_active:
                message = (
                    f'{created_role_label} account created successfully as inactive. '
                    f'Activate it later before first login.'
                )
            else:
                message = f'{created_role_label} account created successfully'

            email_notification_sent = None
            if new_user.email:
                try:
                    from app.utils.email_service import send_account_created_email

                    full_name = f"{(new_user.first_name or '').strip()} {(new_user.last_name or '').strip()}".strip()
                    if not full_name:
                        full_name = new_user.email

                    email_notification_sent = bool(
                        send_account_created_email(
                            to_email=new_user.email,
                            full_name=full_name,
                            role_name='department_head' if created_role_label == 'Department Head' else 'teacher',
                            department_name=department.department_name,
                            is_active=account_is_active,
                            is_approved=account_is_approved,
                        )
                    )
                    if email_notification_sent:
                        message = f'{message}. Account email notification sent.'
                    else:
                        message = f'{message}. Account email notification could not be sent.'
                        logger.warning(
                            f"User account created for user_id={new_user.user_id}, "
                            "but the account-created email was not sent."
                        )
                except Exception as email_error:
                    email_notification_sent = False
                    message = f'{message}. Account email notification could not be sent.'
                    logger.error(
                        f"User account created for user_id={new_user.user_id}, "
                        f"but failed to send account-created email: {str(email_error)}"
                    )

            response = {
                'success': True,
                'message': message,
                'user': new_user.to_dict(),
                'requires_department_approval': requires_department_approval,
            }
            if email_notification_sent is not None:
                response['email_notification_sent'] = email_notification_sent

            return response, 201

        except IntegrityError:
            db.session.rollback()
            return {'success': False, 'message': 'User with this information already exists'}, 409
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating admin-managed user account: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to create user account'}, 500

    @staticmethod
    def get_dashboard_stats():
        """Get dashboard statistics for admin"""
        try:
            stats = {
                'total_users': User.query.count(),
                'total_teachers': User.query.join(Role).filter(Role.role_name == 'teacher').count(),
                'total_departments': Department.query.count(),
                'total_schools': School.query.count(),
                'total_subjects': Subject.query.count(),
                'total_exams': Exam.query.count(),
                'pending_approvals': User.query.filter_by(is_approved=False).count(),
                'pending_exam_approvals': Exam.query.filter(
                    Exam.admin_status == 'pending',
                    Exam.submitted_to_admin.is_(True)
                ).count()
            }
            
            return {
                'success': True,
                'stats': stats
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {str(e)}")
            return {'success': False, 'message': 'Failed to get dashboard stats'}, 500
    
    @staticmethod
    def get_system_logs(page=1, per_page=20):
        """Get system logs (placeholder implementation)"""
        try:
            # This is a placeholder implementation
            # In a real system, you would query a logs table or file
            
            logs = [
                {
                    'id': 1,
                    'timestamp': '2023-01-01 12:00:00',
                    'level': 'INFO',
                    'message': 'System started successfully',
                    'user': 'system'
                },
                {
                    'id': 2,
                    'timestamp': '2023-01-01 12:05:00',
                    'level': 'INFO',
                    'message': 'User logged in',
                    'user': 'john.doe'
                }
            ]
            
            # Simple pagination
            start = (page - 1) * per_page
            end = start + per_page
            paginated_logs = logs[start:end]
            
            return {
                'success': True,
                'logs': paginated_logs,
                'total': len(logs),
                'pages': (len(logs) + per_page - 1) // per_page,
                'current_page': page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting system logs: {str(e)}")
            return {'success': False, 'message': 'Failed to get system logs'}, 500
    
    @staticmethod
    def get_system_settings():
        """Get system settings (placeholder implementation)"""
        try:
            # This is a placeholder implementation
            # In a real system, you would query a settings table
            
            settings = {
                'site_name': 'AWEGen Exam System',
                'site_description': 'AI-Assisted Written Exam Generator',
                'admin_email': 'admin@awegen.com',
                'max_file_size': 52428800,  # 50MB in bytes
                'allowed_file_types': ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt'],
                'session_timeout': 3600,  # 1 hour in seconds
                'maintenance_mode': False
            }
            
            return {
                'success': True,
                'settings': settings
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting system settings: {str(e)}")
            return {'success': False, 'message': 'Failed to get system settings'}, 500
    
    @staticmethod
    def update_system_settings(settings_data):
        """Update system settings (placeholder implementation)"""
        try:
            # This is a placeholder implementation
            # In a real system, you would update a settings table
            
            # Validate settings data
            required_fields = ['site_name', 'admin_email']
            for field in required_fields:
                if field not in settings_data:
                    return {'success': False, 'message': f'Missing required field: {field}'}, 400
            
            # In a real implementation, you would save the settings to the database
            logger.info(f"System settings updated: {settings_data}")
            
            return {
                'success': True,
                'message': 'System settings updated successfully'
            }, 200
            
        except Exception as e:
            logger.error(f"Error updating system settings: {str(e)}")
            return {'success': False, 'message': 'Failed to update system settings'}, 500
    
    @staticmethod
    def get_system_reports():
        """Get system reports (placeholder implementation)"""
        try:
            # This is a placeholder implementation
            # In a real system, you would generate reports from the database
            
            reports = {
                'user_activity': {
                    'total_logins': 1250,
                    'active_users': 320,
                    'new_users': 45
                },
                'exam_activity': {
                    'exams_created': 120,
                    'exams_taken': 850,
                    'average_score': 78.5
                },
                'system_performance': {
                    'uptime': '99.9%',
                    'response_time': '120ms',
                    'error_rate': '0.1%'
                }
            }
            
            return {
                'success': True,
                'reports': reports
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting system reports: {str(e)}")
            return {'success': False, 'message': 'Failed to get system reports'}, 500

    @staticmethod
    def get_exam_password_settings():
        """Get exam download password status for admin."""
        try:
            password = get_exam_download_password()
            masked_password = ''
            if password:
                if len(password) <= 2:
                    masked_password = '*' * len(password)
                else:
                    masked_password = ('*' * (len(password) - 2)) + password[-2:]

            return {
                'success': True,
                'settings': {
                    'is_configured': bool(password),
                    'masked_password': masked_password,
                    'current_password': password,
                    'min_password_length': 4,
                }
            }, 200

        except Exception as e:
            logger.error(f"Error getting exam password settings: {str(e)}")
            return {'success': False, 'message': 'Failed to get exam password settings'}, 500

    @staticmethod
    def update_exam_password(settings_data):
        """Update exam download password used for PDF and DOCX protection."""
        try:
            password_raw = settings_data.get('password') if isinstance(settings_data, dict) else None
            if not isinstance(password_raw, str):
                return {'success': False, 'message': 'password is required'}, 400

            password = password_raw.strip()
            if len(password) < 4:
                return {
                    'success': False,
                    'message': 'Password must be at least 4 characters long'
                }, 400

            set_exam_download_password(password)

            return {
                'success': True,
                'message': 'Exam download password updated successfully'
            }, 200

        except Exception as e:
            logger.error(f"Error updating exam password: {str(e)}")
            return {'success': False, 'message': 'Failed to update exam password'}, 500

    @staticmethod
    def get_departments_with_subjects():
        """Get all departments and their subjects for admin management."""
        try:
            departments = Department.query.order_by(Department.department_name.asc()).all()
            payload = []
            for department in departments:
                subjects = (
                    Subject.query
                    .filter_by(department_id=department.department_id)
                    .order_by(Subject.subject_name.asc())
                    .all()
                )
                payload.append({
                    **department.to_dict(),
                    'subjects': [subject.to_dict() for subject in subjects],
                    'subject_count': len(subjects),
                })

            return {'success': True, 'departments': payload}, 200
        except Exception as e:
            logger.error(f"Error getting departments with subjects: {str(e)}")
            return {'success': False, 'message': 'Failed to get departments and subjects'}, 500

    @staticmethod
    def create_department(department_data):
        """Create a new department."""
        try:
            department_name = (department_data.get('department_name') or '').strip()
            description = (department_data.get('description') or '').strip() or None
            school_id_number = department_data.get('school_id_number')

            if not department_name:
                return {'success': False, 'message': 'department_name is required'}, 400

            # Keep payload simple: if school_id_number is not provided, infer it.
            # Priority:
            # 1) school of the first existing department
            # 2) first school record
            if not school_id_number:
                existing_department = Department.query.order_by(Department.department_id.asc()).first()
                if existing_department:
                    school_id_number = existing_department.school_id_number
                else:
                    first_school = School.query.order_by(School.school_id_number.asc()).first()
                    if first_school:
                        school_id_number = first_school.school_id_number

            if not school_id_number:
                return {
                    'success': False,
                    'message': 'No school available. Create a school first or pass school_id_number.'
                }, 400

            school = School.query.get(school_id_number)
            if not school:
                return {'success': False, 'message': 'School not found'}, 404

            duplicate = (
                Department.query
                .filter(
                    Department.school_id_number == school_id_number,
                    func.lower(Department.department_name) == department_name.lower()
                )
                .first()
            )
            if duplicate:
                return {'success': False, 'message': 'Department already exists'}, 400

            department = Department(
                school_id_number=school_id_number,
                department_name=department_name,
                description=description
            )
            db.session.add(department)
            db.session.commit()

            return {
                'success': True,
                'message': 'Department created successfully',
                'department': department.to_dict()
            }, 201
        except IntegrityError:
            db.session.rollback()
            return {'success': False, 'message': 'Failed to create department'}, 409
        except Exception as e:
            logger.error(f"Error creating department: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to create department'}, 500

    @staticmethod
    def create_subject(subject_data):
        """Create a subject under a department."""
        try:
            department_id = subject_data.get('department_id')
            subject_name = (subject_data.get('subject_name') or '').strip()
            description = (subject_data.get('description') or '').strip() or None

            if not department_id:
                return {'success': False, 'message': 'department_id is required'}, 400
            if not subject_name:
                return {'success': False, 'message': 'subject_name is required'}, 400

            department = Department.query.get(department_id)
            if not department:
                return {'success': False, 'message': 'Department not found'}, 404

            duplicate = (
                Subject.query
                .filter(
                    Subject.department_id == department_id,
                    func.lower(Subject.subject_name) == subject_name.lower()
                )
                .first()
            )
            if duplicate:
                return {'success': False, 'message': 'Subject already exists in this department'}, 400

            subject = Subject(
                subject_name=subject_name,
                department_id=department_id,
                description=description,
            )
            db.session.add(subject)
            db.session.commit()

            return {
                'success': True,
                'message': 'Subject created successfully',
                'subject': subject.to_dict()
            }, 201
        except Exception as e:
            logger.error(f"Error creating subject: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to create subject'}, 500

    @staticmethod
    def update_subject(subject_id, subject_data):
        """Update an existing subject."""
        try:
            subject = Subject.query.get(subject_id)
            if not subject:
                return {'success': False, 'message': 'Subject not found'}, 404

            new_name = subject_data.get('subject_name')
            new_department_id = subject_data.get('department_id', subject.department_id)
            new_description = subject_data.get('description', subject.description)

            if new_name is not None:
                new_name = new_name.strip()
                if not new_name:
                    return {'success': False, 'message': 'subject_name cannot be empty'}, 400
                subject.subject_name = new_name

            if new_description is not None:
                new_description = new_description.strip() if isinstance(new_description, str) else new_description
                subject.description = new_description or None

            if new_department_id != subject.department_id:
                department = Department.query.get(new_department_id)
                if not department:
                    return {'success': False, 'message': 'Department not found'}, 404
                subject.department_id = new_department_id

            duplicate = (
                Subject.query
                .filter(
                    Subject.subject_id != subject.subject_id,
                    Subject.department_id == subject.department_id,
                    func.lower(Subject.subject_name) == subject.subject_name.lower()
                )
                .first()
            )
            if duplicate:
                return {'success': False, 'message': 'Subject already exists in this department'}, 400

            db.session.commit()
            return {
                'success': True,
                'message': 'Subject updated successfully',
                'subject': subject.to_dict()
            }, 200
        except Exception as e:
            logger.error(f"Error updating subject {subject_id}: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update subject'}, 500

    @staticmethod
    def delete_subject(subject_id):
        """Delete a subject if it is not used by modules."""
        try:
            subject = Subject.query.get(subject_id)
            if not subject:
                return {'success': False, 'message': 'Subject not found'}, 404

            # Prevent orphaned module records
            from app.module_processor.models import Module
            in_use = Module.query.filter_by(subject_id=subject_id).first()
            if in_use:
                return {
                    'success': False,
                    'message': 'Cannot delete subject because modules are linked to it'
                }, 409

            db.session.delete(subject)
            db.session.commit()
            return {'success': True, 'message': 'Subject deleted successfully'}, 200
        except IntegrityError:
            db.session.rollback()
            return {
                'success': False,
                'message': 'Cannot delete subject because it is used by other records'
            }, 409
        except Exception as e:
            logger.error(f"Error deleting subject {subject_id}: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to delete subject'}, 500
