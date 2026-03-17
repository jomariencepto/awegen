from app.database import db
from app.auth.models import User, Role
from app.users.models import Department, School, Subject
from app.exam.models import Exam, ExamCategory
from app.utils.logger import get_logger
from app.utils.exam_password import get_exam_download_password, set_exam_download_password
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

logger = get_logger(__name__)


class AdminService:
    @staticmethod
    def get_all_users(page=1, per_page=10):
        """Get all users with pagination"""
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
            logger.error(f"Error getting all users: {str(e)}")
            return {'success': False, 'message': 'Failed to get users'}, 500

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
