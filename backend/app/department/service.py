from app.database import db
from app.auth.models import User, Role
from app.users.models import Department, Subject
from app.exam.models import Exam, ExamQuestion
from app.exam.service import ExamService
from app.module_processor.models import Module, ModuleQuestion
from app.notifications.models import Notification
from app.utils.logger import get_logger
from sqlalchemy import and_, or_, func
import json
import os

logger = get_logger(__name__)


class DepartmentService:
    
    @staticmethod
    def get_all_departments():
        """Get all departments - needed for dropdowns in frontend"""
        try:
            logger.info("Fetching all departments")
            
            departments = Department.query.all()
            
            logger.info(f"Found {len(departments)} departments")
            
            dept_list = []
            for dept in departments:
                try:
                    dept_dict = dept.to_dict()
                except AttributeError:
                    dept_dict = {
                        'id': dept.id if hasattr(dept, 'id') else dept.department_id,
                        'name': (dept.department_name if hasattr(dept, 'department_name') 
                                else dept.dept_name if hasattr(dept, 'dept_name')
                                else dept.name if hasattr(dept, 'name')
                                else f"Department {dept.id}"),
                        'description': dept.description if hasattr(dept, 'description') else None
                    }
                dept_list.append(dept_dict)
            
            dept_list.sort(key=lambda x: x.get('name', ''))
            
            return {
                'success': True,
                'departments': dept_list
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting all departments: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to get departments: {str(e)}'
            }, 500

    @staticmethod
    def create_exam_for_department(exam_data, creator_id):
        """
        Create an exam on behalf of a department user.
        The exam remains editable until the department creator approves it.
        """
        try:
            creator = User.query.get(creator_id)
            if not creator:
                return {'success': False, 'message': 'User not found'}, 404

            if not creator.department_id:
                return {
                    'success': False,
                    'message': 'User is not assigned to a department'
                }, 400

            logger.info(f"Department user {creator_id} creating exam for department {creator.department_id}")

            result, status_code = ExamService.create_exam(
                exam_data,
                teacher_id=creator_id,
                auto_approve=False,
                department_id=creator.department_id
            )

            if isinstance(result, dict) and result.get('success'):
                result['message'] = 'Exam created successfully. Edit questions, then approve when ready.'
                result['admin_status'] = 'draft'

            return result, status_code

        except Exception as e:
            logger.error(f"Error creating department exam: {str(e)}", exc_info=True)
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to create department exam: {str(e)}'
            }, 500

    @staticmethod
    def save_created_exam(exam_id, editor_id, exam_data=None):
        """
        Save a department-created exam and move it into the department pending queue.
        This keeps the teacher review flow separate from the department-created flow.
        """
        try:
            editor = User.query.get(editor_id)
            if not editor:
                return {'success': False, 'message': 'User not found'}, 404

            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            editor_role = (editor.role or '').lower()
            if editor_role not in ['department', 'department_head', 'admin']:
                return {'success': False, 'message': 'Insufficient permissions'}, 403

            if editor_role != 'admin':
                if not editor.department_id:
                    return {'success': False, 'message': 'User is not assigned to a department'}, 400
                if exam.teacher_id != editor.user_id:
                    return {
                        'success': False,
                        'message': 'Only the department user who created this exam can save it.'
                    }, 403
                if exam.department_id and exam.department_id != editor.department_id:
                    return {
                        'success': False,
                        'message': 'Exam does not belong to your department.'
                    }, 403

            if (exam.admin_status or '').lower() == 'approved':
                return {'success': False, 'message': 'Approved exams can no longer be changed'}, 409

            save_payload = exam_data if isinstance(exam_data, dict) else {}
            result, status_code = ExamService.update_exam(exam_id, save_payload)
            if status_code != 200 or not result.get('success'):
                return result, status_code

            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found after save'}, 404

            exam.department_id = exam.department_id or editor.department_id
            exam.admin_status = 'pending'
            exam.submitted_to_admin = False
            exam.submitted_at = None
            exam.sent_to_department = False
            exam.is_published = False
            exam.reviewed_by = None
            exam.reviewed_at = None
            exam.admin_feedback = None
            exam.rejection_reason = None

            db.session.commit()

            return {
                'success': True,
                'message': 'Exam saved and moved to Pending Approvals.',
                'exam': exam.to_dict(),
                'exam_admin_status': exam.admin_status,
            }, 200

        except Exception as e:
            logger.error(f"Error saving department-created exam: {str(e)}", exc_info=True)
            db.session.rollback()
            return {
                'success': False,
                'message': f'Failed to save department exam: {str(e)}'
            }, 500

    @staticmethod
    def approve_created_exam(exam_id, approver_id):
        """
        Finalize a department-created exam after question edits.
        This stays separate from the teacher submit-for-approval flow.
        """
        try:
            from datetime import datetime

            approver = User.query.get(approver_id)
            if not approver:
                return {'success': False, 'message': 'User not found'}, 404

            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            approver_role = (approver.role or '').lower()
            if approver_role not in ['department', 'department_head', 'admin']:
                return {'success': False, 'message': 'Insufficient permissions'}, 403

            if approver_role != 'admin':
                if not approver.department_id:
                    return {'success': False, 'message': 'User is not assigned to a department'}, 400
                if exam.teacher_id != approver.user_id:
                    return {
                        'success': False,
                        'message': 'Only the department user who created this exam can approve it.'
                    }, 403
                if exam.department_id and exam.department_id != approver.department_id:
                    return {
                        'success': False,
                        'message': 'Exam does not belong to your department.'
                    }, 403

            if exam.admin_status == 'approved':
                return {'success': False, 'message': 'Exam is already approved'}, 409

            question_count = ExamQuestion.query.filter_by(exam_id=exam_id).count()
            if question_count == 0:
                return {
                    'success': False,
                    'message': 'Cannot approve exam without questions.'
                }, 400

            flagged_count = ExamQuestion.query.filter(
                ExamQuestion.exam_id == exam_id,
                ExamQuestion.feedback.isnot(None),
                func.length(func.trim(ExamQuestion.feedback)) > 0,
            ).count()
            if flagged_count > 0:
                return {
                    'success': False,
                    'message': 'Clear question feedback before approving this exam.'
                }, 400

            exam.department_id = exam.department_id or approver.department_id
            exam.submitted_to_admin = True
            exam.admin_status = 'approved'
            exam.submitted_at = exam.submitted_at or datetime.utcnow()
            exam.is_published = True
            exam.sent_to_department = False
            exam.reviewed_by = approver_id
            exam.reviewed_at = datetime.utcnow()
            exam.admin_feedback = None
            exam.rejection_reason = None

            db.session.commit()

            return {
                'success': True,
                'message': 'Exam approved successfully',
                'exam': exam.to_dict()
            }, 200

        except Exception as e:
            logger.error(f"Error approving department-created exam: {str(e)}", exc_info=True)
            db.session.rollback()
            return {
                'success': False,
                'message': f'Failed to approve department exam: {str(e)}'
            }, 500

    @staticmethod
    def get_department_dashboard(department_id):
        """Get dashboard statistics for a department"""
        try:
            logger.info(f"Fetching dashboard stats for department_id: {department_id}")
            
            teacher_role = Role.query.filter_by(role_name='teacher').first()

            # Only teachers that belong to this department.
            teacher_ids = []
            teacher_ids_scope = []
            if teacher_role:
                # Teachers formally assigned to this department (used for exam scope)
                teacher_ids_scope = [
                    user_id for (user_id,) in db.session.query(User.user_id).filter(
                        User.role_id == teacher_role.role_id,
                        User.department_id == department_id
                    ).all()
                ]
                # Dashboard teacher counts must match department ownership strictly.
                teacher_ids = list(teacher_ids_scope)
            else:
                teacher_ids_scope = []

            # Base query for this department's exams (assigned to dept or created by its teachers)
            exam_scope = Exam.query.filter(
                or_(
                    Exam.department_id == department_id,
                    Exam.teacher_id.in_(teacher_ids_scope) if teacher_ids_scope else False
                )
            )

            # Pending for department:
            # - admin_status == 'pending' (admin review)
            # - OR already admin-approved but sent_to_department awaiting department action
            pending_count = exam_scope.filter(
                or_(
                    Exam.admin_status == 'pending',
                    Exam.sent_to_department.is_(True)
                )
            ).count()

            # Approved exams for this department:
            # 1) Explicitly assigned to this department, OR
            # 2) Legacy rows with NULL department_id created by teachers in this department.
            approved_count = Exam.query.filter(
                Exam.admin_status == 'approved',
                or_(
                    Exam.department_id == department_id,
                    and_(
                        Exam.department_id.is_(None),
                        Exam.teacher_id.in_(teacher_ids_scope) if teacher_ids_scope else False
                    )
                )
            ).count()

            # "Total Number of Exams" on department dashboard should show approved exams only.
            total_exams = approved_count

            # Teachers pending approval (matches Manage Users source: dept + unassigned).
            pending_users_count = User.query.filter(
                User.user_id.in_(teacher_ids) if teacher_ids else False,
                User.is_approved.is_(False)
            ).count()
             
            logger.info(
                f"Department {department_id}: Total exams = {total_exams}, "
                f"Approved exams = {approved_count}, Pending exams = {pending_count}, Pending users = {pending_users_count}"
            )
             
            stats = {
                'total_teachers': len(teacher_ids),
                'total_subjects': Subject.query.filter_by(
                    department_id=department_id
                ).count(),
                'total_exams': total_exams,
                'approved_exams': approved_count,
                'pending_exams': pending_count,
                'pending_users': pending_users_count
            }
            
            return {
                'success': True,
                'stats': stats
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting department dashboard: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to get department dashboard: {str(e)}'
            }, 500
    
    @staticmethod
    def get_department_exams(department_id, status=None, page=1, per_page=10):
        """
        Get exams for a department.
        Shows exams from teachers in this department OR submitted to this department.
        """
        try:
            logger.info(f"Fetching exams for department_id: {department_id}, status: {status}")
            
            teacher_role = Role.query.filter_by(role_name='teacher').first()
            teacher_ids_scope = []
            
            if teacher_role:
                teacher_ids_scope = [
                    user_id for (user_id,) in db.session.query(User.user_id).filter(
                        User.department_id == department_id,
                        User.role_id == teacher_role.role_id
                    ).all()
                ]
                logger.info(f"Found {len(teacher_ids_scope)} teachers in department {department_id}")
            
            query = Exam.query.filter(
                or_(
                    Exam.department_id == department_id,
                    Exam.teacher_id.in_(teacher_ids_scope) if teacher_ids_scope else False
                )
            )
            
            if status:
                status_lower = status.lower()
                
                if status_lower == 'pending':
                    # Pending includes admin pending OR admin-approved but sent to department and not yet handled
                    query = query.filter(
                        or_(
                            Exam.admin_status == 'pending',
                            Exam.sent_to_department.is_(True)
                        )
                    )
                elif status_lower == 'approved':
                    # Approved exams for this department:
                    # - explicit department ownership, or
                    # - legacy NULL-department exams from teachers in this department.
                    query = query.filter(
                        Exam.admin_status == 'approved',
                        or_(
                            Exam.department_id == department_id,
                            and_(
                                Exam.department_id.is_(None),
                                Exam.teacher_id.in_(teacher_ids_scope) if teacher_ids_scope else False
                            )
                        )
                    )
                elif status_lower == 'rejected':
                    query = query.filter(Exam.admin_status == 'rejected')
                elif status_lower in ['revision_required', 'revision']:
                    query = query.filter(Exam.admin_status == 'revision_required')
                else:
                    query = query.filter(Exam.admin_status == status)
            else:
                query = query.filter(Exam.admin_status != 'draft')
            
            query = query.order_by(Exam.created_at.desc())
            
            total_count = query.count()
            logger.info(f"Found {total_count} exams matching criteria")
            
            exams = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            teacher_ids = list({exam.teacher_id for exam in exams.items if exam.teacher_id})
            teacher_lookup = {}
            if teacher_ids:
                teachers = User.query.filter(User.user_id.in_(teacher_ids)).all()
                teacher_lookup = {
                    teacher.user_id: (
                        f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or "Unknown Teacher"
                    )
                    for teacher in teachers
                }

            exam_list = []
            for exam in exams.items:
                try:
                    exam_dict = exam.to_dict()
                    exam_dict['teacher_name'] = teacher_lookup.get(exam.teacher_id, "Unknown Teacher")
                    exam_list.append(exam_dict)
                    
                except Exception as item_error:
                    logger.error(f"Error processing exam {exam.exam_id}: {str(item_error)}")
                    continue
            
            return {
                'success': True,
                'exams': exam_list,
                'total': exams.total,
                'pages': exams.pages,
                'current_page': exams.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting department exams: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to get department exams: {str(e)}'
            }, 500
    
    @staticmethod
    def get_department_teachers(department_id, page=1, per_page=10, include_unassigned=False):
        """Get teachers in a department. If include_unassigned is True, also include teachers with no department."""
        try:
            logger.info(f"Fetching teachers for department_id: {department_id}")
            
            teacher_role = Role.query.filter_by(role_name='teacher').first()
            
            if not teacher_role:
                return {
                    'success': True,
                    'teachers': [],
                    'total': 0,
                    'pages': 0,
                    'current_page': 1
                }, 200
            
            query = User.query.filter(
                User.role_id == teacher_role.role_id
            )

            if include_unassigned:
                query = query.filter(
                    (User.department_id == department_id) | (User.department_id.is_(None))
                )
            else:
                query = query.filter(User.department_id == department_id)

            query = query.order_by(User.last_name, User.first_name)
            
            teachers = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            teacher_list = []
            for teacher in teachers.items:
                try:
                    teacher_dict = teacher.to_dict()
                    teacher_list.append(teacher_dict)
                except Exception as e:
                    logger.error(f"Error processing teacher {teacher.user_id}: {str(e)}")
                    continue
            
            logger.info(f"Found {len(teacher_list)} teachers for department {department_id}")
            
            return {
                'success': True,
                'teachers': teacher_list,
                'total': teachers.total,
                'pages': teachers.pages,
                'current_page': teachers.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting department teachers: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to get teachers: {str(e)}'
            }, 500
    
    @staticmethod
    def get_department_subjects(department_id):
        """Get subjects for a department"""
        try:
            logger.info(f"Fetching subjects for department_id: {department_id}")
            
            subjects = Subject.query.filter_by(
                department_id=department_id
            ).order_by(Subject.subject_name).all()
            
            subject_list = []
            for subject in subjects:
                try:
                    subject_dict = subject.to_dict()
                except AttributeError:
                    subject_dict = {
                        'id': subject.id if hasattr(subject, 'id') else subject.subject_id,
                        'name': (subject.subject_name if hasattr(subject, 'subject_name')
                                else subject.name if hasattr(subject, 'name')
                                else f"Subject {subject.id}"),
                        'department_id': subject.department_id
                    }
                subject_list.append(subject_dict)
            
            logger.info(f"Found {len(subject_list)} subjects for department {department_id}")
            
            return {
                'success': True,
                'subjects': subject_list
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting department subjects: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to get subjects: {str(e)}'
            }, 500

    @staticmethod
    def get_department_modules(department_id):
        """
        Get all modules for a department - FIXED VERSION
        ✅ NOW INCLUDES is_archived FIELD
        """
        try:
            logger.info(f"📚 Fetching modules for department_id: {department_id}")
            
            # Get all subjects for this department
            subjects = Subject.query.filter_by(
                department_id=department_id
            ).all()
            
            subject_ids = [s.subject_id for s in subjects]
            subject_lookup = {subject.subject_id: subject for subject in subjects}
            
            logger.info(f"Found {len(subject_ids)} subjects for department {department_id}")
            
            if not subject_ids:
                logger.info(f"No subjects found for department {department_id}")
                return {
                    'success': True,
                    'modules': [],
                    'message': 'No subjects found for this department'
                }, 200
            
            # Get all modules for these subjects
            modules = Module.query.filter(
                Module.subject_id.in_(subject_ids)
            ).order_by(Module.created_at.desc()).all()

            module_ids = [module.module_id for module in modules]
            question_counts = {}
            if module_ids:
                rows = (
                    db.session.query(
                        ModuleQuestion.module_id,
                        ModuleQuestion.difficulty_level,
                        func.count(ModuleQuestion.question_id).label('cnt')
                    )
                    .filter(ModuleQuestion.module_id.in_(module_ids))
                    .group_by(ModuleQuestion.module_id, ModuleQuestion.difficulty_level)
                    .all()
                )
                for row in rows:
                    mid = row.module_id
                    if mid not in question_counts:
                        question_counts[mid] = {'total': 0, 'easy': 0, 'medium': 0, 'hard': 0}
                    diff = row.difficulty_level or 'medium'
                    question_counts[mid][diff] = row.cnt
                    question_counts[mid]['total'] += row.cnt

            teacher_ids = [module.teacher_id for module in modules if module.teacher_id]
            teacher_lookup = {
                teacher.user_id: teacher
                for teacher in User.query.filter(User.user_id.in_(teacher_ids)).all()
            } if teacher_ids else {}
            
            logger.info(f"Found {len(modules)} modules for department {department_id}")
            
            # Enrich module data with subject and user info
            modules_list = []
            for module in modules:
                try:
                    # Get subject info
                    subject = subject_lookup.get(module.subject_id)
                    subject_name = subject.subject_name if subject else 'Unknown Subject'
                    department_name = (
                        subject.department.department_name
                        if subject and getattr(subject, 'department', None)
                        else None
                    )
                    
                    # ✅ FIXED: Use teacher_id (not uploaded_by)
                    teacher = teacher_lookup.get(module.teacher_id)
                    if teacher:
                        teacher_name = f"{teacher.first_name} {teacher.last_name}".strip()
                        if not teacher_name:
                            teacher_name = teacher.email or 'Unknown'
                    else:
                        teacher_name = 'Unknown'
                    
                    # ✅ FIXED: Extract filename from file_path
                    file_name = None
                    if module.file_path:
                        # Extract filename from path (handles both / and \)
                        file_name = os.path.basename(module.file_path)
                    qc = question_counts.get(module.module_id, {'total': 0, 'easy': 0, 'medium': 0, 'hard': 0})
                    
                    module_dict = {
                        'module_id': module.module_id,
                        'title': module.title,
                        'description': module.description,
                        'subject_id': module.subject_id,
                        'subject_name': subject_name,
                        'department_name': department_name,
                        'teacher_id': module.teacher_id,
                        'uploaded_by': module.teacher_id,  # Map teacher_id to uploaded_by for frontend
                        'uploaded_by_name': teacher_name,
                        'file_name': file_name,  # Extracted from file_path
                        'file_path': module.file_path,
                        'file_type': module.file_type if hasattr(module, 'file_type') else None,
                        'file_size': module.file_size if hasattr(module, 'file_size') else None,
                        'teaching_hours': module.teaching_hours if hasattr(module, 'teaching_hours') else None,
                        'processing_status': module.processing_status if hasattr(module, 'processing_status') else 'pending',
                        'upload_date': module.upload_date.isoformat() if module.upload_date else None,
                        'created_at': module.created_at.isoformat() if module.created_at else None,
                        
                        # ✅✅✅ CRITICAL FIX: Added is_archived field ✅✅✅
                        'is_archived': module.is_archived if hasattr(module, 'is_archived') else False,
                        'question_count': qc['total'],
                        'question_breakdown': {
                            'easy': qc['easy'],
                            'medium': qc['medium'],
                            'hard': qc['hard'],
                        },
                    }
                    
                    modules_list.append(module_dict)
                    
                except Exception as e:
                    logger.error(f"Error processing module {module.module_id}: {str(e)}")
                    continue
            
            logger.info(f"Successfully processed {len(modules_list)} modules")
            
            return {
                'success': True,
                'modules': modules_list
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting department modules: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get modules: {str(e)}'
            }, 500
    
    # ===================================================================
    # EXAM APPROVAL
    # ===================================================================
    
    @staticmethod
    def approve_department_exam(exam_id, data, approver_id):
        """
        Approve, reject, or request revision for an exam
        data should contain:
          - action (approve/reject/revision_required)
          - feedback (optional overall note)
          - question_reviews (required for revision_required)
        """
        try:
            logger.info(f"Processing exam approval for exam_id: {exam_id} by approver: {approver_id}")
            
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            review_locked = (
                exam.admin_status in ['approved', 'rejected', 'revision_required']
                and not exam.sent_to_department
            )
            if review_locked:
                return {
                    'success': False,
                    'message': 'Review already submitted for this exam. Feedback can only be sent once per review cycle.'
                }, 409
            
            action = data.get('action', '').lower()
            feedback = data.get('feedback', '')
            question_reviews = data.get('question_reviews') or []
            
            if action not in ['approve', 'reject', 'revision_required']:
                return {
                    'success': False, 
                    'message': 'Invalid action. Must be approve, reject, or revision_required'
                }, 400

            exam_questions = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(ExamQuestion.question_id).all()
            if not exam_questions:
                return {
                    'success': False,
                    'message': 'No questions found for this exam'
                }, 400

            existing_flagged = sum(1 for q in exam_questions if (q.feedback or '').strip())
            if action == 'approve' and existing_flagged > 0:
                return {
                    'success': False,
                    'message': 'Cannot approve while some questions are flagged for revision.'
                }, 400

            flagged_count = existing_flagged
            approved_count = len(exam_questions) - existing_flagged

            if action == 'revision_required':
                if not question_reviews:
                    return {
                        'success': False,
                        'message': 'Submit the full question review file in one request before sending feedback.'
                    }, 400

                normalized_reviews = {}
                for item in question_reviews:
                    try:
                        qid = int(item.get('question_id'))
                    except Exception:
                        return {
                            'success': False,
                            'message': 'Each review row must include a valid question_id.'
                        }, 400
                    normalized_reviews[qid] = {
                        'status': str(item.get('status', '')).strip().lower(),
                        'feedback': str(item.get('feedback', '')).strip(),
                    }

                question_ids = {q.question_id for q in exam_questions}
                if set(normalized_reviews.keys()) != question_ids:
                    return {
                        'success': False,
                        'message': 'Question review must include all generated questions exactly once.'
                    }, 400

                flagged_count = 0
                approved_count = 0
                for question in exam_questions:
                    row = normalized_reviews[question.question_id]
                    has_feedback = bool(row['feedback'])
                    status = row['status'] or ('revision_required' if has_feedback else 'correct')

                    if status in ['correct', 'approved'] and not has_feedback:
                        question.feedback = None
                        approved_count += 1
                        continue

                    if has_feedback:
                        question.feedback = row['feedback']
                        flagged_count += 1
                    else:
                        return {
                            'success': False,
                            'message': f'Question {question.question_id} is marked for revision but has no feedback.'
                        }, 400

                if flagged_count == 0:
                    return {
                        'success': False,
                        'message': 'Please add feedback to at least one question before requesting revision.'
                    }, 400
             
            # Update exam status and keep feedback in canonical fields.
            if action == 'approve':
                exam.admin_status = 'approved'
                exam.is_published = True
                exam.rejection_reason = None
                exam.admin_feedback = feedback or None
            elif action == 'reject':
                exam.admin_status = 'rejected'
                exam.rejection_reason = feedback or None
            elif action == 'revision_required':
                exam.admin_status = 'revision_required'
                if feedback:
                    exam.admin_feedback = feedback
                else:
                    exam.admin_feedback = (
                        f'Question feedback submitted: {flagged_count} flagged, '
                        f'{approved_count} marked correct.'
                    )
                exam.rejection_reason = None
             
            exam.reviewed_by = approver_id
            from datetime import datetime
            exam.reviewed_at = datetime.utcnow()
            # Department has acted; clear the "sent_to_department" flag to remove from pending list
            exam.sent_to_department = False

            # Notify teacher about the department decision.
            teacher_message = None
            if action == 'approved' or action == 'approve':
                teacher_message = f'Your exam "{exam.title}" was approved by the department.'
            elif action == 'reject':
                teacher_message = f'Your exam "{exam.title}" was rejected by the department.'
            elif action == 'revision_required':
                teacher_message = (
                    f'Your exam "{exam.title}" needs revision from the department. '
                    f'{flagged_count} question(s) were flagged; {approved_count} marked correct.'
                )

            if feedback:
                teacher_message = f"{teacher_message} Feedback: {feedback}"

            if exam.teacher_id and teacher_message:
                db.session.add(
                    Notification(
                        user_id=exam.teacher_id,
                        type='approval',
                        text=teacher_message,
                        read=False,
                    )
                )
             
            db.session.commit()
            
            logger.info(f"Exam {exam_id} {action} by approver {approver_id}")
            
            return {
                'success': True,
                'message': f'Exam {action} successfully',
                'exam': exam.to_dict()
            }, 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error approving exam: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False, 
                'message': f'Failed to approve exam: {str(e)}'
            }, 500

    # ===================================================================
    # EXAM PREVIEW & TOS for Department Users
    # ===================================================================
    
    @staticmethod
    def get_exam_preview(exam_id):
        """
        Get full exam preview with questions for department review.
        Returns exam details and all questions.
        """
        try:
            logger.info(f"Fetching exam preview for exam_id: {exam_id}")
            
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Get all questions
            questions = ExamQuestion.query.filter_by(
                exam_id=exam_id
            ).order_by(ExamQuestion.question_id).all()
            
            questions_data = []
            for q in questions:
                q_dict = q.to_dict()
                
                # Parse options if they're stored as JSON string
                if q_dict.get('options'):
                    if isinstance(q_dict['options'], str):
                        try:
                            q_dict['options'] = json.loads(q_dict['options'])
                        except Exception:
                            q_dict['options'] = []
                
                questions_data.append(q_dict)
            
            # Get teacher info
            teacher = User.query.get(exam.teacher_id)
            teacher_name = f"{teacher.first_name} {teacher.last_name}" if teacher else "Unknown"
            
            exam_dict = exam.to_dict()
            exam_dict['teacher_name'] = teacher_name
            
            logger.info(f"Exam preview loaded: {len(questions_data)} questions")
            
            return {
                'success': True,
                'exam': exam_dict,
                'questions': questions_data,
                'total_questions': len(questions_data)
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting exam preview: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get exam preview: {str(e)}'
            }, 500

    @staticmethod
    def get_exam_tos(exam_id):
        """
        IMPROVED: Generate TOS with better structure and error handling.
        
        Tries to use TOSGenerator if available, falls back to basic analysis.
        """
        try:
            logger.info(f"=" * 80)
            logger.info(f"📊 GENERATING TOS FOR EXAM {exam_id}")
            logger.info(f"=" * 80)
            
            # Get exam
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Get questions
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            
            if not questions:
                return {
                    'success': False,
                    'message': 'No questions found for this exam'
                }, 404
            
            logger.info(f"Found {len(questions)} questions for exam {exam_id}")
            
            # ============================================================
            # TRY: Use TOSGenerator (preferred method)
            # ============================================================
            try:
                from app.exam.tos_generator import TOSGenerator
                from app.exam.bloom_classifier import BloomClassifier
                logger.info("✅ TOSGenerator available, using advanced TOS generation")

                # Convert questions to dict format
                questions_data = []
                for q in questions:
                    q_dict = {
                        'question_text': q.question_text,
                        'question_type': q.question_type,
                        'difficulty_level': q.difficulty_level or 'medium',
                        'points': q.points or 1,
                        'bloom_level': q.bloom_level or 'remembering',
                        'topic': q.topic or 'General'
                    }

                    # Parse options if needed
                    if q.options:
                        if isinstance(q.options, str):
                            try:
                                q_dict['options'] = json.loads(q.options)
                            except Exception:
                                q_dict['options'] = []
                        else:
                            q_dict['options'] = q.options

                    questions_data.append(q_dict)

                # Classify questions using BloomClassifier (same as teacher route)
                bloom_classifier = BloomClassifier()
                for q in questions_data:
                    if not q.get('bloom_level') or q['bloom_level'] == 'remembering':
                        q['bloom_level'] = bloom_classifier.classify_question(q['question_text'])

                # Extract topics from questions
                topics = list(set([q['topic'] for q in questions_data]))
                if not topics:
                    topics = ['General']
                
                # Generate TOS
                tos_generator = TOSGenerator()
                exam_config = {
                    'title': exam.title,
                    'duration_minutes': exam.duration_minutes or 60,
                    'total_questions': len(questions)
                }
                
                tos = tos_generator.generate_tos(questions_data, topics, exam_config)
                
                logger.info("✅ TOS generated successfully using TOSGenerator")
                
                # Build response with full TOS data
                cognitive_levels = ['remembering', 'understanding', 'applying', 'analyzing', 'evaluating', 'creating']
                
                return {
                    'success': True,
                    'exam_id': exam_id,
                    'exam_title': exam.title,
                    'tos': tos,
                    'cognitive_levels': [
                        {
                            'name': level,
                            'total': tos.get('cognitive_distribution', {}).get(level, 0)
                        }
                        for level in cognitive_levels
                    ],
                    'topics': [
                        {
                            'name': topic,
                            'total': sum(tos.get('topic_cognitive_matrix', {}).get(topic, {}).values())
                        }
                        for topic in topics
                    ],
                    'matrix': [
                        {
                            'topic_id': idx,
                            'topic_name': topic,
                            'distribution': [
                                tos.get('topic_cognitive_matrix', {}).get(topic, {}).get(level, 0)
                                for level in cognitive_levels
                            ],
                            'total': sum(tos.get('topic_cognitive_matrix', {}).get(topic, {}).values())
                        }
                        for idx, topic in enumerate(topics)
                    ],
                    'difficulty_distribution': tos.get('difficulty_distribution', {}),
                    'question_type_distribution': tos.get('question_type_distribution', {}),
                    'summary': tos.get('summary', {})
                }, 200
                        
            except ImportError as e:
                logger.warning(f"⚠️ TOSGenerator not available: {str(e)}")
                logger.info("Using fallback TOS generation")
            except Exception as tos_error:
                logger.warning(f"⚠️ TOSGenerator failed: {str(tos_error)}")
                logger.info("Using fallback TOS generation")
            
            # ============================================================
            # FALLBACK: Build basic TOS from question data
            # ============================================================
            logger.info("📊 Using fallback TOS generation from question data")
            
            difficulty_dist = {'easy': 0, 'medium': 0, 'hard': 0}
            type_dist = {}
            total_points = 0
            
            for q in questions:
                # Count by difficulty
                diff = q.difficulty_level or 'medium'
                difficulty_dist[diff] = difficulty_dist.get(diff, 0) + 1
                
                # Count by type
                qtype = q.question_type or 'unknown'
                type_dist[qtype] = type_dist.get(qtype, 0) + 1
                
                # Sum points
                total_points += (q.points or 1)
            
            total_questions = len(questions)
            
            logger.info(f"✅ Fallback TOS complete:")
            logger.info(f"   Total Questions: {total_questions}")
            logger.info(f"   Total Points: {total_points}")
            logger.info(f"   Difficulty: {difficulty_dist}")
            logger.info(f"   Types: {type_dist}")
            logger.info("=" * 80)
            
            return {
                'success': True,
                'exam_id': exam_id,
                'exam_title': exam.title,
                'tos': {
                    'difficulty_distribution': difficulty_dist,
                    'question_type_distribution': type_dist,
                    'summary': {
                        'total_questions': total_questions,
                        'total_points': total_points,
                        'average_points_per_question': round(total_points / total_questions, 2) if total_questions > 0 else 0
                    }
                },
                'cognitive_levels': [],
                'topics': [],
                'matrix': [],
                'difficulty_distribution': difficulty_dist,
                'question_type_distribution': type_dist,
                'summary': {
                    'total_questions': total_questions,
                    'total_points': total_points,
                    'average_points_per_question': round(total_points / total_questions, 2) if total_questions > 0 else 0
                }
            }, 200
            
        except Exception as e:
            logger.error(f"❌ Error generating TOS for exam {exam_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to generate TOS: {str(e)}'
            }, 500
