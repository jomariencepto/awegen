import json
from app.database import db
from app.exam.models import Exam, ExamQuestion, ExamCategory, ExamSubmission, ExamAnswer, ExamModule
from app.exam.schemas import (
    ExamSchema, ExamCreateSchema, ExamUpdateSchema, ExamSubmitSchema, 
    ExamApproveSchema, ExamSendToDepartmentSchema, QuestionCreateSchema, 
    QuestionUpdateSchema, ExamSubmissionCreateSchema, ExamAnswerCreateSchema,
    ExamCategorySchema, ExamQuestionSchema, ExamSubmissionSchema, ExamAnswerSchema
)
from app.exam.tos_generator import TOSGenerator
from app.auth.models import User
from app.notifications.models import Notification
from app.utils.logger import get_logger
from datetime import datetime
from sqlalchemy import and_, or_, func
from marshmallow import ValidationError
import threading

# Process-level ExamGenerator cache — models (spaCy, sentence-transformers, T5)
# are loaded once and reused across requests.  Per-exam mutable state is reset
# by generate_exam() → reset_question_tracking() at the start of every call.
_exam_generator_lock = threading.Lock()
_exam_generator_instance = None


def _get_exam_generator():
    """Return the cached ExamGenerator (thread-safe, lazy init)."""
    global _exam_generator_instance
    if _exam_generator_instance is None:
        with _exam_generator_lock:
            if _exam_generator_instance is None:
                from app.exam.exam_generator import ExamGenerator
                _exam_generator_instance = ExamGenerator()
    return _exam_generator_instance
logger = get_logger(__name__)


class ExamService:
    @staticmethod
    def _build_question_count_map(exam_ids):
        """Return {exam_id: question_count} for the provided exam IDs."""
        if not exam_ids:
            return {}

        rows = (
            db.session.query(
                ExamQuestion.exam_id,
                func.count(ExamQuestion.question_id).label('question_count'),
            )
            .filter(ExamQuestion.exam_id.in_(exam_ids))
            .group_by(ExamQuestion.exam_id)
            .all()
        )
        return {row.exam_id: int(row.question_count or 0) for row in rows}

    @staticmethod
    def _calculate_module_question_targets(modules, total_questions):
        """Distribute total questions across modules using weighted largest remainder."""
        if not modules or total_questions <= 0:
            return {}

        weighted = []
        for module in modules:
            module_id = int(module['module_id'])
            weight = max(0.0, float(module.get('teaching_hours', 0) or 0))
            weighted.append((module_id, weight))

        total_weight = sum(weight for _, weight in weighted)
        if total_weight <= 0:
            base = total_questions // len(weighted)
            remainder = total_questions % len(weighted)
            targets = {}
            for idx, (module_id, _) in enumerate(weighted):
                targets[module_id] = base + (1 if idx < remainder else 0)
            return targets

        raw = [(module_id, (weight / total_weight) * total_questions) for module_id, weight in weighted]
        floors = {module_id: int(value) for module_id, value in raw}
        assigned = sum(floors.values())
        remainder = total_questions - assigned

        fractions = sorted(
            ((module_id, value - floors[module_id]) for module_id, value in raw),
            key=lambda item: item[1],
            reverse=True
        )

        idx = 0
        while remainder > 0 and fractions:
            module_id = fractions[idx % len(fractions)][0]
            floors[module_id] += 1
            remainder -= 1
            idx += 1

        return floors

    @staticmethod
    def _apply_module_coverage_to_contents(contents, coverage_percent):
        """Best-effort trim of module content according to selected coverage percent."""
        if not contents:
            return []

        coverage = max(0.0, min(100.0, float(coverage_percent or 0)))
        if coverage <= 0:
            return []
        if coverage >= 100:
            return list(contents)

        total_chars = sum(len((item or {}).get('content_text', '') or '') for item in contents)
        if total_chars <= 0:
            return list(contents)

        target_chars = max(1, int(total_chars * (coverage / 100.0)))
        selected = []
        accumulated = 0

        for content_item in contents:
            text = (content_item or {}).get('content_text', '') or ''
            if not text:
                continue
            remaining = target_chars - accumulated
            if remaining <= 0:
                break

            if len(text) <= remaining:
                selected.append(dict(content_item))
                accumulated += len(text)
                continue

            trimmed = dict(content_item)
            trimmed['content_text'] = text[:remaining]
            selected.append(trimmed)
            accumulated += remaining
            break

        return selected if selected else [dict(contents[0])]

    @staticmethod
    def _resolve_exam_department_id(exam):
        """Resolve department_id for exam workflow notifications."""
        if not exam:
            return None

        if exam.department_id:
            return exam.department_id

        teacher = exam.teacher or (User.query.get(exam.teacher_id) if exam.teacher_id else None)
        if teacher and teacher.department_id:
            return teacher.department_id

        module = exam.module
        if module and module.subject and module.subject.department_id:
            return module.subject.department_id

        if module and module.subject_id:
            try:
                from app.users.models import Subject
                subject = Subject.query.get(module.subject_id)
                if subject and subject.department_id:
                    return subject.department_id
            except Exception:
                pass

        return None

    @staticmethod
    def _create_notifications_for_users(user_ids, notification_type, message):
        if not user_ids or not message:
            return 0

        created_count = 0
        unique_user_ids = []
        seen = set()
        for user_id in user_ids:
            try:
                uid = int(user_id)
            except Exception:
                continue
            if uid in seen:
                continue
            seen.add(uid)
            unique_user_ids.append(uid)

        for uid in unique_user_ids:
            db.session.add(
                Notification(
                    user_id=uid,
                    type=notification_type,
                    text=message,
                    read=False,
                )
            )
            created_count += 1

        return created_count

    @staticmethod
    def _notify_department_exam_submission(exam):
        """Notify department users when a teacher submits an exam for review."""
        try:
            department_id = ExamService._resolve_exam_department_id(exam)
            if not department_id:
                logger.warning(
                    f"Notification skipped for exam {getattr(exam, 'exam_id', 'unknown')}: no department resolved"
                )
                return 0

            recipients = User.query.filter(
                User.department_id == department_id,
                User.is_active.is_(True),
                User.role.in_(['department', 'department_head'])
            ).all()
            recipient_ids = [u.user_id for u in recipients]
            if not recipient_ids:
                logger.warning(
                    f"Notification skipped for exam {exam.exam_id}: no active department recipients in department {department_id}"
                )
                return 0

            teacher = exam.teacher or (User.query.get(exam.teacher_id) if exam.teacher_id else None)
            teacher_name = "A teacher"
            if teacher:
                teacher_name = f"{teacher.first_name or ''} {teacher.last_name or ''}".strip() or teacher.username

            message = f'{teacher_name} submitted exam "{exam.title}" for review.'
            return ExamService._create_notifications_for_users(
                recipient_ids,
                'exam_submission',
                message
            )
        except Exception as notify_err:
            logger.error(f"Failed to queue department submission notification: {str(notify_err)}")
            return 0

    @staticmethod
    def _notify_department_exam_sent(exam, sender_id):
        """Notify department users when an exam is explicitly sent to department."""
        try:
            department_id = exam.department_id or ExamService._resolve_exam_department_id(exam)
            if not department_id:
                logger.warning(
                    f"Notification skipped for exam {getattr(exam, 'exam_id', 'unknown')}: no destination department"
                )
                return 0

            recipients = User.query.filter(
                User.department_id == department_id,
                User.is_active.is_(True),
                User.role.in_(['department', 'department_head'])
            ).all()
            recipient_ids = [u.user_id for u in recipients]
            if not recipient_ids:
                logger.warning(
                    f"Notification skipped for exam {exam.exam_id}: no active department recipients in department {department_id}"
                )
                return 0

            sender = User.query.get(sender_id)
            sender_name = "A user"
            if sender:
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or sender.username

            message = f'{sender_name} sent exam "{exam.title}" to your department for review.'
            return ExamService._create_notifications_for_users(
                recipient_ids,
                'exam_submission',
                message
            )
        except Exception as notify_err:
            logger.error(f"Failed to queue department send notification: {str(notify_err)}")
            return 0

    @staticmethod
    def _notify_teacher_exam_decision(exam, status, feedback=None, reviewer_label='admin'):
        """Notify teacher when exam decision changes."""
        try:
            if not exam or not exam.teacher_id:
                return 0

            status_value = str(status or '').strip().lower()
            if status_value == 'approved':
                message = f'Your exam "{exam.title}" was approved by the {reviewer_label}.'
            elif status_value == 'rejected':
                message = f'Your exam "{exam.title}" was rejected by the {reviewer_label}.'
            elif status_value == 'revision_required':
                message = f'Your exam "{exam.title}" needs revision based on {reviewer_label} review.'
            else:
                message = f'Your exam "{exam.title}" has a new review update from the {reviewer_label}.'

            feedback_text = str(feedback or '').strip()
            if feedback_text:
                message = f"{message} Feedback: {feedback_text}"

            return ExamService._create_notifications_for_users(
                [exam.teacher_id],
                'approval',
                message
            )
        except Exception as notify_err:
            logger.error(f"Failed to queue teacher decision notification: {str(notify_err)}")
            return 0

    @staticmethod
    def get_all_exams(page=1, per_page=10, status=None):
        """Get all exams with pagination (Admin Dashboard), optional admin_status filter"""
        try:
            query = Exam.query
            if status:
                query = query.filter_by(admin_status=status)

            exams = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'success': True,
                'exams': [exam.to_dict() for exam in exams.items],
                'total': exams.total,
                'pages': exams.pages,
                'current_page': exams.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting all exams: {str(e)}")
            return {'success': False, 'message': 'Failed to get exams'}, 500

    @staticmethod
    def create_exam(exam_data, teacher_id, auto_approve=False, approver_id=None, department_id=None):
        try:
            from app.module_processor.saved_module import SavedModuleService

            # Remove teacher_id from exam_data if present (it's passed separately)
            exam_data_copy = exam_data.copy()
            if 'teacher_id' in exam_data_copy:
                del exam_data_copy['teacher_id']
            
            # Validate input data
            schema = ExamCreateSchema()
            validated_data = schema.load(exam_data_copy)
            
            logger.info(f"Validated exam data: {validated_data}")

            requested_duration = int(validated_data.get('duration_minutes') or 0)
            allocated_minutes = validated_data.get('allocated_minutes')
            if allocated_minutes is not None:
                allocated_minutes = int(allocated_minutes)
                if requested_duration > 0 and allocated_minutes > requested_duration:
                    return {
                        'success': False,
                        'message': (
                            f'Allocated time ({allocated_minutes}) must not exceed '
                            f'exam duration ({requested_duration}).'
                        ),
                        'error_code': 'DURATION_EXCEEDED',
                        'allocated_minutes': allocated_minutes,
                        'duration_minutes': requested_duration
                    }, 400

            configured_points = sum(
                int(qt.get('count', 0)) * int(qt.get('points', 0))
                for qt in validated_data.get('question_types_details', [])
            )
            score_limit = validated_data.get('score_limit')
            if score_limit is not None:
                score_limit = int(score_limit)
                if configured_points != score_limit:
                    return {
                        'success': False,
                        'message': (
                            f'Total points ({configured_points}) must exactly match '
                            f'score limit ({score_limit}).'
                        ),
                        'error_code': 'SCORE_LIMIT_CONFIG_MISMATCH',
                        'configured_points': configured_points,
                        'score_limit': score_limit
                    }, 400
            
            module_coverage_mode = validated_data.get('module_coverage_mode', 'hours')
            module_ids = [m['module_id'] for m in validated_data['modules']]

            provided_targets = validated_data.get('module_question_targets') or []
            if provided_targets:
                module_question_targets = {
                    int(target['module_id']): int(target['count'])
                    for target in provided_targets
                }
            else:
                module_question_targets = ExamService._calculate_module_question_targets(
                    validated_data['modules'],
                    validated_data['num_questions']
                )

            # Get content from all modules
            all_module_content = []
            for module_info in validated_data['modules']:
                module_id = module_info['module_id']
                teaching_hours = module_info['teaching_hours']
                
                module_content_result, _ = SavedModuleService.get_module_content(module_id)
                if not module_content_result['success']:
                    return {
                        'success': False, 
                        'message': f'Failed to get content for module {module_id}'
                    }, 400
                
                module_contents = module_content_result['contents']
                if module_coverage_mode == 'percent':
                    module_contents = ExamService._apply_module_coverage_to_contents(
                        module_contents,
                        teaching_hours
                    )

                # Add teaching hours/coverage to each content item
                for content_item in module_contents:
                    content_item['teaching_hours'] = teaching_hours
                    content_item['module_id'] = module_id
                
                all_module_content.extend(module_contents)
            
            logger.info(f"Retrieved content from {len(validated_data['modules'])} modules")
            
            # Prepare exam config for generator
            exam_config = {
                'title': validated_data['title'],
                'description': validated_data['description'],
                'num_questions': validated_data['num_questions'],
                'question_types': validated_data['question_types'],
                'question_types_with_points': validated_data.get('question_types_with_points', []),
                'question_types_details': validated_data.get('question_types_details', []),
                'score_limit': validated_data.get('score_limit'),
                'cognitive_distribution': validated_data.get('cognitive_distribution'),
                'duration_minutes': validated_data['duration_minutes'],
                'allocated_minutes': validated_data.get('allocated_minutes'),
                'passing_score': validated_data['passing_score'],
                'total_hours': validated_data['total_hours'],
                'module_coverage_mode': module_coverage_mode,
                'module_question_targets': module_question_targets,
                # Pass module IDs so the generator can pull pre-processed DB questions
                'module_ids': module_ids,
            }
            
            # Generate exam (cached per-process — models loaded once)
            exam_generator = _get_exam_generator()
            exam_result = exam_generator.generate_exam(all_module_content, exam_config)
            
            if not exam_result['success']:
                status_code = 400 if exam_result.get('error_code') == 'SCORE_TARGET_MISMATCH' else 500
                return {
                    'success': False, 
                    'message': exam_result.get('message', 'Failed to generate exam'),
                    'error_code': exam_result.get('error_code'),
                    'generated_points': exam_result.get('generated_points'),
                    'target_points': exam_result.get('target_points'),
                }, status_code
            
            logger.info(f"Generated {len(exam_result['questions'])} questions")
            
            # Create exam record - use first module as primary module
            primary_module_id = validated_data['modules'][0]['module_id']
            
            exam = Exam(
                title=validated_data['title'],
                description=validated_data['description'],
                module_id=primary_module_id,  # Primary module for backward compatibility
                teacher_id=teacher_id,
                category_id=validated_data['category_id'],
                start_time=validated_data.get('start_time'),
                end_time=validated_data.get('end_time'),
                duration_minutes=validated_data['duration_minutes'],
                total_questions=len(exam_result['questions']),
                passing_score=validated_data['passing_score']
            )
            db.session.add(exam)
            db.session.flush()  # Get exam_id

            logger.info(f"Created exam record with ID: {exam.exam_id}")

            # Save ExamModule associations (many-to-many, deduped)
            for mid in dict.fromkeys(module_ids):  # preserve order, drop duplicates
                db.session.add(ExamModule(exam_id=exam.exam_id, module_id=mid))
            logger.info(f"Saved {len(module_ids)} ExamModule associations")

            # Auto-approve flow for department-created exams
            if auto_approve:
                exam.submitted_to_admin = True
                exam.admin_status = 'approved'
                exam.submitted_at = datetime.utcnow()
                exam.is_published = True
                exam.sent_to_department = False
                if department_id:
                    exam.department_id = department_id
                if approver_id:
                    exam.reviewed_by = approver_id
                    exam.reviewed_at = datetime.utcnow()

            # IMPORTANT: Save questions with ALL required fields
            for question_data in exam_result['questions']:
                # Ensure options is properly formatted as JSON string
                options_json = None
                if question_data.get('options'):
                    if isinstance(question_data['options'], list):
                        options_json = json.dumps(question_data['options'])
                    else:
                        options_json = question_data['options']
                
                # Create the question with all fields
                # _module_question_id / _image_id are set by the generator when
                # the question came from the module_questions table (problem_solving DB pull)
                question = ExamQuestion(
                    exam_id=exam.exam_id,
                    module_question_id=question_data.get('_module_question_id'),
                    question_text=question_data['question_text'],
                    question_type=question_data['question_type'],
                    difficulty_level=question_data.get('difficulty_level', 'medium'),
                    bloom_level=question_data.get('bloom_level', 'remembering'),
                    topic=question_data.get('topic', 'General'),
                    options=options_json,  # Store as JSON string
                    correct_answer=question_data['correct_answer'],
                    points=question_data.get('points', 1),
                    feedback=question_data.get('feedback', None),
                    image_id=question_data.get('_image_id'),
                )
                db.session.add(question)
                
                logger.info(f"Added question: {question_data['question_text'][:50]}... with answer: {question_data['correct_answer']}")
            
            # Commit all changes
            db.session.commit()
            
            logger.info(f"Successfully created exam {exam.exam_id} with {len(exam_result['questions'])} questions")
            logger.info("All questions and answers have been saved to the database")
            
            # Build image_id -> module_id map so generated preview can render images immediately
            image_module_by_id = {}
            image_ids = list({q.get('_image_id') for q in exam_result['questions'] if q.get('_image_id')})
            if image_ids:
                try:
                    from app.module_processor.models import ModuleImage
                    image_rows = ModuleImage.query.filter(ModuleImage.image_id.in_(image_ids)).all()
                    image_module_by_id = {img.image_id: img.module_id for img in image_rows}
                except Exception as img_err:
                    logger.warning(f"Failed to resolve image module IDs for generated exam response: {img_err}")

            # Construct strict JSON return object
            formatted_questions = []
            for q in exam_result['questions']:
                image_id = q.get('_image_id')
                formatted_questions.append({
                    "question_text": q.get('question_text'),
                    "question_type": q.get('question_type'),
                    "options": q.get('options', []),
                    "correct_answer": q.get('correct_answer'),
                    "difficulty_level": q.get('difficulty_level'),
                    "bloom_level": q.get('bloom_level'),
                    "points": q.get('points'),
                    "image_id": image_id,
                    "image_module_id": image_module_by_id.get(image_id)
                })
            
            response = {
                'success': True,
                'message': 'Exam created successfully',
                'exam_id': exam.exam_id,
                'questions': formatted_questions,
                'tos': exam_result.get('tos', {})
            }
            if exam_result.get('warning'):
                response['warning'] = exam_result['warning']
            return response, 201
            
        except ValidationError as e:
            logger.error(f"Validation error creating exam: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'message': 'Validation error in exam configuration',
                'errors': e.messages
            }, 400

        except Exception as e:
            logger.error(f"Error creating exam: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return {
                'success': False, 
                'message': f'Failed to create exam: {str(e)}'
            }, 500
    
    @staticmethod
    def get_exam_by_id(exam_id):
        try:
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Get questions
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            
            # Get question count
            question_count = len(questions)
            
            # Format exam data
            exam_data = exam.to_dict()
            exam_data['question_count'] = question_count
            module_ids = [em.module_id for em in (exam.exam_modules or [])]
            if not module_ids and exam.module_id:
                module_ids = [exam.module_id]
            exam_data['module_ids'] = module_ids

            # Build image_id -> module_id map for rendering question images.
            image_module_by_id = {}
            image_ids = [q.image_id for q in questions if q.image_id]
            if image_ids:
                try:
                    from app.module_processor.models import ModuleImage
                    image_rows = ModuleImage.query.filter(ModuleImage.image_id.in_(image_ids)).all()
                    image_module_by_id = {img.image_id: img.module_id for img in image_rows}
                except Exception as img_err:
                    logger.warning(f"Failed to resolve image module IDs for exam {exam_id}: {img_err}")
            
            # Format questions with parsed options
            formatted_questions = []
            for q in questions:
                q_dict = q.to_dict()
                # Parse options if they're stored as JSON string
                if q_dict.get('options') and isinstance(q_dict['options'], str):
                    try:
                        q_dict['options'] = json.loads(q_dict['options'])
                    except:
                        q_dict['options'] = []
                # Clean squished text in MCQ options
                if q_dict.get('options') and isinstance(q_dict['options'], list):
                    q_dict['options'] = [ExamGenerator._fix_spaced_characters(o) if isinstance(o, str) else o for o in q_dict['options']]
                q_dict['image_module_id'] = image_module_by_id.get(q_dict.get('image_id'))
                formatted_questions.append(q_dict)
            
            exam_data['questions'] = formatted_questions
            
            return {
                'success': True,
                'exam': exam_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting exam by ID: {str(e)}")
            return {'success': False, 'message': 'Failed to get exam'}, 500
    
    @staticmethod
    def get_exams_by_teacher(teacher_id, page=1, per_page=10):
        """Get exams created by a specific teacher"""
        try:
            exams = (
                Exam.query
                .filter_by(teacher_id=teacher_id)
                .order_by(Exam.updated_at.desc(), Exam.created_at.desc(), Exam.exam_id.desc())
                .paginate(
                page=page,
                per_page=per_page,
                error_out=False
                )
            )
            
            question_counts = ExamService._build_question_count_map(
                [exam.exam_id for exam in exams.items]
            )
            exams_data = []
            for exam in exams.items:
                exam_dict = exam.to_dict()
                exam_dict['question_count'] = question_counts.get(exam.exam_id, 0)
                exams_data.append(exam_dict)
            
            return {
                'success': True,
                'exams': exams_data,
                'total': exams.total,
                'pages': exams.pages,
                'current_page': exams.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting exams by teacher: {str(e)}")
            return {'success': False, 'message': 'Failed to get teacher exams'}, 500

    @staticmethod
    def get_saved_exams(teacher_id, page=1, per_page=10):
        """
        Get saved (draft/non-submitted) exams for a teacher
        Returns exams that haven't been submitted to admin yet
        """
        try:
            logger.info(f"Fetching saved exams for teacher {teacher_id}")
            
            # Query for exams by this teacher that are still drafts
            query = Exam.query.filter_by(teacher_id=teacher_id)
            
            # Filter for draft exams (not submitted to admin)
            query = query.filter(
                (Exam.submitted_to_admin == False) | (Exam.submitted_to_admin == None)
            )
            
            # Order by most recent first
            query = query.order_by(Exam.created_at.desc())
            
            # Get total count
            total = query.count()
            
            logger.info(f"Found {total} saved exams for teacher {teacher_id}")
            
            # Paginate
            exams = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Build response
            question_counts = ExamService._build_question_count_map(
                [exam.exam_id for exam in exams.items]
            )
            exams_list = []
            for exam in exams.items:
                try:
                    exam_dict = exam.to_dict()
                    exam_dict['question_count'] = question_counts.get(exam.exam_id, 0)
                    exams_list.append(exam_dict)
                    
                except Exception as e:
                    logger.error(f"Error processing exam {exam.exam_id}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'exams': exams_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': exams.pages
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting saved exams: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get saved exams: {str(e)}'
            }, 500

    @staticmethod
    def get_teacher_dashboard_summary(teacher_id):
        """Return lightweight dashboard stats and recent exams for a teacher."""
        try:
            from app.module_processor.models import Module

            base_query = Exam.query.filter_by(teacher_id=teacher_id)
            total_exams = base_query.count()
            pending_actions = (
                base_query.filter(Exam.admin_status.in_(['pending', 'revision_required'])).count()
            )
            revision_required = (
                base_query.filter(Exam.admin_status == 'revision_required').count()
            )
            total_modules = Module.query.filter(
                Module.teacher_id == teacher_id,
                or_(Module.is_archived == 0, Module.is_archived.is_(None))
            ).count()

            recent_exam_rows = (
                base_query
                .order_by(Exam.updated_at.desc(), Exam.created_at.desc(), Exam.exam_id.desc())
                .limit(5)
                .all()
            )
            question_counts = ExamService._build_question_count_map(
                [exam.exam_id for exam in recent_exam_rows]
            )

            recent_exams = []
            for exam in recent_exam_rows:
                exam_dict = exam.to_dict()
                exam_dict['question_count'] = question_counts.get(exam.exam_id, 0)
                recent_exams.append(exam_dict)

            return {
                'success': True,
                'stats': {
                    'total_exams': total_exams,
                    'total_modules': total_modules,
                    'pending_actions': pending_actions,
                    'revision_required': revision_required,
                },
                'recent_exams': recent_exams,
            }, 200

        except Exception as e:
            logger.error(f"Error getting teacher dashboard summary: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to get dashboard summary'
            }, 500
    @staticmethod
    def update_exam(exam_id, exam_data):
        """
        ================================================================
        ✅ UPDATE EXAM AND SAVE CORRECT ANSWERS TO exam_answers TABLE
        ================================================================
        When "Save Exam" is clicked, this method:
        1. Updates exam details
        2. Creates a submission record for the teacher
        3. Saves all correct answers to exam_answers table
        ================================================================
        """
        try:
            logger.info(f"=" * 80)
            logger.info(f"📝 UPDATING EXAM {exam_id}")
            logger.info(f"=" * 80)
            
            schema = ExamUpdateSchema()
            validated_data = schema.load(exam_data)
            
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Update exam fields
            for field, value in validated_data.items():
                if hasattr(exam, field):
                    setattr(exam, field, value)
            
            db.session.commit()
            
            logger.info(f"✅ Exam details updated")
            
            # ================================================================
            # ✅ SAVE CORRECT ANSWERS TO exam_answers TABLE
            # ================================================================
            
            logger.info(f"📝 Saving correct answers to exam_answers table...")
            
            # Get all questions for this exam
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            
            if questions:
                # ✅ CHECK IF SUBMISSION EXISTS FOR THIS EXAM (by teacher)
                submission = ExamSubmission.query.filter_by(
                    exam_id=exam_id,
                    user_id=exam.teacher_id
                ).first()
                
                if not submission:
                    # ✅ CREATE SUBMISSION RECORD
                    submission = ExamSubmission(
                        exam_id=exam_id,
                        user_id=exam.teacher_id,
                        start_time=datetime.utcnow(),
                        submit_time=datetime.utcnow(),
                        score=None,  # Not applicable for answer key
                        total_points=sum(q.points or 1 for q in questions),
                        is_completed=True
                    )
                    db.session.add(submission)
                    db.session.flush()  # Get submission_id
                    
                    logger.info(f"✅ Created submission {submission.submission_id} for exam {exam_id}")
                
                # ✅ DELETE OLD ANSWERS (prevent duplicates)
                ExamAnswer.query.filter_by(submission_id=submission.submission_id).delete()
                
                logger.info(f"🗑️  Deleted old answers (if any)")
                
                # ✅ CREATE NEW ANSWER RECORDS
                answers_created = 0
                
                for question in questions:
                    # Create answer with correct answer from question
                    answer = ExamAnswer(
                        submission_id=submission.submission_id,  # Link to submission
                        question_id=question.question_id,        # Question ID
                        answer_text=question.correct_answer,     # Correct answer
                        is_correct=True,                         # Mark as correct
                        points_earned=question.points or 1       # Full points
                    )
                    db.session.add(answer)
                    answers_created += 1
                
                db.session.commit()
                
                logger.info(f"=" * 80)
                logger.info(f"✅ SUCCESS!")
                logger.info(f"   Exam ID: {exam_id}")
                logger.info(f"   Submission ID: {submission.submission_id}")
                logger.info(f"   Answers Saved: {answers_created}")
                logger.info(f"   Teacher ID: {exam.teacher_id}")
                logger.info(f"=" * 80)
            else:
                logger.info(f"⚠️  No questions found for exam {exam_id}")
            
            return {
                'success': True,
                'message': 'Exam updated and answers saved successfully',
                'exam': exam.to_dict(),
                'answers_saved': len(questions) if questions else 0
            }, 200
            
        except Exception as e:
            logger.error(f"❌ Error updating exam: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update exam'}, 500
    
    @staticmethod
    def delete_exam(exam_id):
        """Delete an exam and all related data (questions, submissions, answers)"""
        try:
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # FIX: Delete in correct order to respect foreign key constraints
            # 1. Delete answers (depends on submissions and questions)
            submissions = ExamSubmission.query.filter_by(exam_id=exam_id).all()
            for submission in submissions:
                ExamAnswer.query.filter_by(submission_id=submission.submission_id).delete()
            
            # 2. Delete submissions (depends on exam)
            ExamSubmission.query.filter_by(exam_id=exam_id).delete()
            
            # 3. Delete questions (depends on exam)
            ExamQuestion.query.filter_by(exam_id=exam_id).delete()
            
            # 4. Delete exam
            db.session.delete(exam)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Exam deleted successfully'
            }, 200
            
        except Exception as e:
            logger.error(f"Error deleting exam: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to delete exam'}, 500

    @staticmethod
    def submit_exam_for_approval(submit_data):
        """Submit exam for admin approval - ENHANCED with better error handling"""
        try:
            logger.info(f"🔵 Submitting exam for approval: {submit_data}")
            
            # Validate schema
            schema = ExamSubmitSchema()
            validated_data = schema.load(submit_data)
            
            exam_id = validated_data['exam_id']
            logger.info(f"🔵 Exam ID: {exam_id}")
            
            # Get exam
            exam = Exam.query.get(exam_id)
            
            if not exam:
                logger.error(f"❌ Exam {exam_id} not found in database")
                return {'success': False, 'message': 'Exam not found'}, 404
            
            logger.info(f"🔵 Found exam: {exam.title}")
            
            # Check if exam has questions
            question_count = ExamQuestion.query.filter_by(exam_id=exam_id).count()
            logger.info(f"🔵 Question count: {question_count}")
            
            if question_count == 0:
                logger.error(f"❌ Exam {exam_id} has no questions")
                return {
                    'success': False,
                    'message': 'Cannot submit exam without questions. Please add at least one question to the exam.'
                }, 400
            
            # Check if already submitted and pending
            if exam.submitted_to_admin and exam.admin_status == 'pending':
                logger.warning(f"⚠️ Exam {exam_id} already submitted and pending")
                return {
                    'success': False,
                    'message': 'Exam is already submitted and pending approval'
                }, 400
            
            # Update exam status
            logger.info(f"🔵 Updating exam status to pending")
            target_department_id = validated_data.get('department_id')
            if target_department_id is not None:
                try:
                    from app.users.models import Department
                    target_department_id = int(target_department_id)
                    target_department = Department.query.get(target_department_id)
                    if not target_department:
                        return {
                            'success': False,
                            'message': f'Department {target_department_id} not found'
                        }, 400
                    exam.department_id = target_department_id
                except Exception as dept_err:
                    logger.error(f"Invalid target department on submit: {dept_err}")
                    return {
                        'success': False,
                        'message': 'Invalid department selected for this exam'
                    }, 400

            exam.submitted_to_admin = True
            exam.admin_status = 'pending'
            exam.submitted_at = datetime.utcnow()
            exam.instructor_notes = validated_data.get('instructor_notes', '')
            notified_count = ExamService._notify_department_exam_submission(exam)
            if notified_count:
                logger.info(f"Queued {notified_count} department submission notification(s) for exam {exam_id}")

            # Commit changes
            db.session.commit()
            
            logger.info(f"✅ Exam {exam_id} '{exam.title}' submitted successfully")
            logger.info(f"✅ Status: submitted_to_admin={exam.submitted_to_admin}, admin_status={exam.admin_status}")
            
            return {
                'success': True,
                'message': 'Exam submitted for approval successfully',
                'exam': exam.to_dict()
            }, 200
            
        except ValidationError as e:
            logger.error(f"❌ Validation error: {str(e)}")
            logger.error(f"❌ Validation details: {e.messages}")
            db.session.rollback()
            return {
                'success': False, 
                'message': f'Validation error: {e.messages}'
            }, 400
            
        except Exception as e:
            logger.error(f"❌ Error submitting exam for approval: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return {
                'success': False, 
                'message': f'Failed to submit exam: {str(e)}'
            }, 500

    @staticmethod
    def approve_exam(approve_data, admin_id):
        """Approve or reject exam (Admin only)"""
        try:
            schema = ExamApproveSchema()
            validated_data = schema.load(approve_data)
            
            exam_id = validated_data['exam_id']
            status = validated_data['status']
            feedback = validated_data.get('feedback', '')
            
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            if status == 'approved':
                exam.admin_status = 'approved'
                exam.is_published = True
                exam.admin_feedback = feedback
            elif status == 'rejected':
                exam.admin_status = 'rejected'
                exam.rejection_reason = feedback
            elif status == 'revision_required':
                exam.admin_status = 'revision_required'
                exam.admin_feedback = feedback
            
            exam.reviewed_by = admin_id
            exam.reviewed_at = datetime.utcnow()
            notified_count = ExamService._notify_teacher_exam_decision(
                exam=exam,
                status=status,
                feedback=feedback,
                reviewer_label='admin'
            )
            if notified_count:
                logger.info(f"Queued {notified_count} teacher decision notification(s) for exam {exam_id}")
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Exam {status} successfully',
                'exam': exam.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error approving exam: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to approve exam'}, 500

    @staticmethod
    def send_exam_to_department(send_data, sender_id):
        """Send approved exam to a department. Allow admin or owning teacher."""
        try:
            from app.users.models import Subject

            # Allow callers to omit department_id; fill from sender's dept if present
            _payload = send_data.copy() if isinstance(send_data, dict) else {}
            if not _payload.get('department_id'):
                sender = User.query.get(sender_id)
                if sender and sender.department_id:
                    _payload['department_id'] = sender.department_id
            # Pre-fill from module's subject department if still missing and exam_id is present
            if not _payload.get('department_id') and _payload.get('exam_id'):
                try:
                    exam_prefetch = Exam.query.get(int(_payload['exam_id']))
                    if exam_prefetch and exam_prefetch.module and exam_prefetch.module.subject_id:
                        subj = Subject.query.get(exam_prefetch.module.subject_id)
                        if subj and subj.department_id:
                            _payload['department_id'] = subj.department_id
                except Exception:
                    pass
            
            schema = ExamSendToDepartmentSchema()
            validated_data = schema.load(_payload)
            
            exam_id = validated_data['exam_id']
            department_id = validated_data.get('department_id')
            notes = validated_data.get('notes', '')
            
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Fallback: derive department from exam.module -> subject.department
            if not department_id:
                module = exam.module  # relationship
                if module and module.subject_id:
                    subject = Subject.query.get(module.subject_id)
                    if subject and subject.department_id:
                        department_id = subject.department_id
            # Fallback: use exam.department_id if already set
            if not department_id and exam.department_id:
                department_id = exam.department_id
            
            # Permission: admin can send any; teacher can only send their own exam
            if exam.teacher_id != sender_id:
                sender = User.query.get(sender_id)
                sender_role = (sender.role or '').lower() if sender else ''
                if sender_role not in ('admin', 'department_head'):
                    return {'success': False, 'message': 'Unauthorized to send this exam'}, 403
            
            # Verify exam is in a sendable state (approved or pending)
            if exam.admin_status not in ('approved', 'pending'):
                return {
                    'success': False,
                    'message': 'Exam must be approved or pending to send to department'
                }, 400
            
            # Ensure we have a destination department
            if not department_id:
                return {
                    'success': False,
                    'message': 'Department is required to send exam (no department found for sender, exam, or module)'
                }, 400

            # Update exam
            exam.sent_to_department = True
            exam.department_id = department_id
            exam.department_notes = notes
            exam.sent_to_department_at = datetime.utcnow()
            notified_count = ExamService._notify_department_exam_sent(exam, sender_id)
            if notified_count:
                logger.info(f"Queued {notified_count} department send notification(s) for exam {exam_id}")
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Exam sent to department successfully',
                'exam': exam.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error sending exam to department: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to send exam to department'}, 500

    @staticmethod
    def get_pending_approvals(page=1, per_page=10):
        """Get exams pending approval"""
        try:
            exams = Exam.query.filter_by(
                admin_status='pending'
            ).paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            return {
                'success': True,
                'exams': [exam.to_dict() for exam in exams.items],
                'total': exams.total,
                'pages': exams.pages,
                'current_page': exams.page
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {str(e)}")
            return {'success': False, 'message': 'Failed to get pending approvals'}, 500

    @staticmethod
    def get_exam_questions(exam_id):
        """Get all questions for an exam"""
        try:
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            
            formatted_questions = []
            for q in questions:
                q_dict = q.to_dict()
                # Clean squished text artifacts from stored questions
                qt = q_dict.get('question_text', '')
                if qt:
                    q_dict['question_text'] = ExamGenerator._fix_spaced_characters(qt)
                ans = q_dict.get('correct_answer', '')
                if ans and ans not in ('True', 'False'):
                    q_dict['correct_answer'] = ExamGenerator._fix_spaced_characters(ans)
                # Parse options if stored as JSON string
                if q_dict.get('options') and isinstance(q_dict['options'], str):
                    try:
                        q_dict['options'] = json.loads(q_dict['options'])
                    except:
                        q_dict['options'] = []
                formatted_questions.append(q_dict)
            
            return {
                'success': True,
                'questions': formatted_questions
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting exam questions: {str(e)}")
            return {'success': False, 'message': 'Failed to get exam questions'}, 500

    @staticmethod
    def add_questions_to_exam(exam_id, questions_data):
        """Add multiple questions to an exam"""
        try:
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            added_questions = []
            for q_data in questions_data:
                # Validate each question
                schema = QuestionCreateSchema()
                validated = schema.load(q_data)
                
                # Create question
                question = ExamQuestion(
                    exam_id=exam_id,
                    question_text=q_data['question_text'],
                    question_type=q_data['question_type'],
                    difficulty_level=q_data.get('difficulty_level', 'medium'),
                    bloom_level=q_data.get('bloom_level', 'remembering'),
                    topic=q_data.get('topic', 'General'),
                    options=json.dumps(q_data.get('options', [])),
                    correct_answer=q_data['correct_answer'],
                    points=q_data.get('points', 1)
                )
                db.session.add(question)
                added_questions.append(question)
            
            # Update total questions
            exam.total_questions = ExamQuestion.query.filter_by(exam_id=exam_id).count() + len(added_questions)
            
            db.session.commit()
            
            return {
                'success': True,
                'message': f'Added {len(added_questions)} questions',
                'questions': [q.to_dict() for q in added_questions]
            }, 201
            
        except Exception as e:
            logger.error(f"Error adding questions: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to add questions'}, 500

    @staticmethod
    def add_question_to_exam(exam_id, question_data):
        """Add a single question to an exam"""
        try:
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            schema = QuestionCreateSchema()
            validated_data = schema.load(question_data)

            options_json = None
            if validated_data.get('options'):
                if isinstance(validated_data['options'], list):
                    options_json = json.dumps(validated_data['options'])
                else:
                    options_json = validated_data['options']

            question = ExamQuestion(
                exam_id=exam_id,
                question_text=validated_data['question_text'],
                question_type=validated_data['question_type'],
                difficulty_level=validated_data.get('difficulty_level', 'medium'),
                bloom_level=validated_data.get('bloom_level', 'remembering'),
                topic=validated_data.get('topic', 'General'),
                options=options_json,
                correct_answer=validated_data['correct_answer'],
                points=validated_data.get('points', 1)
            )
            db.session.add(question)

            # Update total questions count
            exam.total_questions = ExamQuestion.query.filter_by(exam_id=exam_id).count() + 1

            db.session.commit()

            return {
                'success': True,
                'message': 'Question added successfully',
                'question': question.to_dict()
            }, 201

        except Exception as e:
            logger.error(f"Error adding question to exam: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to add question'}, 500

    @staticmethod
    def update_question(question_id, question_data):
        """Update a specific question"""
        try:
            schema = QuestionUpdateSchema()
            validated_data = schema.load(question_data)
            
            question = ExamQuestion.query.get(question_id)
            if not question:
                return {'success': False, 'message': 'Question not found'}, 404

            if 'image_id' in validated_data:
                image_id = validated_data.get('image_id')
                if image_id is not None:
                    from app.module_processor.models import ModuleImage
                    image = ModuleImage.query.get(image_id)
                    if not image:
                        return {
                            'success': False,
                            'message': f'Image {image_id} not found'
                        }, 400

                    # Keep image assignment scoped to modules used by this exam.
                    exam_module_ids = {em.module_id for em in (question.exam.exam_modules or [])}
                    if not exam_module_ids and question.exam.module_id:
                        exam_module_ids = {question.exam.module_id}
                    if exam_module_ids and image.module_id not in exam_module_ids:
                        return {
                            'success': False,
                            'message': 'Selected image does not belong to this exam modules'
                        }, 400

            # For MCQ edits, require explicit valid correct answer from provided/current options.
            effective_question_type = validated_data.get('question_type', question.question_type)
            should_validate_mcq = (
                effective_question_type == 'multiple_choice' and
                any(field in validated_data for field in ('options', 'correct_answer', 'question_type'))
            )
            if should_validate_mcq:
                if 'options' in validated_data:
                    candidate_options = validated_data.get('options') or []
                else:
                    if isinstance(question.options, str):
                        try:
                            candidate_options = json.loads(question.options or '[]')
                        except Exception:
                            candidate_options = []
                    elif isinstance(question.options, list):
                        candidate_options = question.options
                    else:
                        candidate_options = []

                normalized_options = [
                    str(opt).strip()
                    for opt in candidate_options
                    if str(opt).strip()
                ]

                if len(normalized_options) < 2:
                    return {
                        'success': False,
                        'message': 'Multiple Choice must have at least 2 options'
                    }, 400
                if len(normalized_options) > 5:
                    return {
                        'success': False,
                        'message': 'Multiple Choice can only have up to 5 options'
                    }, 400

                normalized_unique_count = len({opt.lower() for opt in normalized_options})
                if normalized_unique_count != len(normalized_options):
                    return {
                        'success': False,
                        'message': 'Multiple Choice options must be unique'
                    }, 400

                candidate_correct = validated_data.get('correct_answer', question.correct_answer)
                normalized_correct = (candidate_correct or '').strip()
                if not normalized_correct:
                    return {
                        'success': False,
                        'message': 'Multiple Choice requires a selected correct answer'
                    }, 400
                if normalized_correct not in normalized_options:
                    return {
                        'success': False,
                        'message': 'Correct answer must match one of the options'
                    }, 400

                validated_data['options'] = normalized_options
                validated_data['correct_answer'] = normalized_correct
             
            # Update fields and track whether the teacher/admin actually changed content.
            has_content_change = False
            for field, value in validated_data.items():
                if field == 'options' and isinstance(value, list):
                    serialized_options = json.dumps(value)
                    if question.options != serialized_options:
                        has_content_change = True
                    setattr(question, field, serialized_options)
                elif hasattr(question, field):
                    if getattr(question, field) != value:
                        has_content_change = True
                    setattr(question, field, value)

            # Auto-clear department feedback once question content is updated by teacher/admin.
            if has_content_change and question.feedback:
                question.feedback = None

            # When a revision-required exam is edited, mark it as revised.
            if has_content_change and question.exam and question.exam.admin_status == 'revision_required':
                question.exam.admin_status = 'Re-Used'
             
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Question updated successfully',
                'question': question.to_dict(),
                'exam_admin_status': question.exam.admin_status if question.exam else None,
                'exam_admin_feedback': question.exam.admin_feedback if question.exam else None,
            }, 200

        except ValidationError as e:
            return {'success': False, 'message': str(e)}, 400
             
        except Exception as e:
            logger.error(f"Error updating question: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update question'}, 500

    @staticmethod
    def update_question_feedback(question_id, feedback_data):
        """Update feedback for a specific question"""
        try:
            question = ExamQuestion.query.get(question_id)
            if not question:
                return {'success': False, 'message': 'Question not found'}, 404
            
            question.feedback = feedback_data.get('feedback', '')
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Feedback updated successfully',
                'question': question.to_dict()
            }, 200
            
        except Exception as e:
            logger.error(f"Error updating question feedback: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to update feedback'}, 500

    @staticmethod
    def delete_question(question_id):
        """Delete a specific question"""
        try:
            question = ExamQuestion.query.get(question_id)
            if not question:
                return {'success': False, 'message': 'Question not found'}, 404
            
            exam_id = question.exam_id
            
            # FIX: Also delete any answers referencing this question
            ExamAnswer.query.filter_by(question_id=question_id).delete()
            
            db.session.delete(question)
            
            # Update total questions count
            exam = Exam.query.get(exam_id)
            if exam:
                exam.total_questions = ExamQuestion.query.filter_by(exam_id=exam_id).count()
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Question deleted successfully'
            }, 200
            
        except Exception as e:
            logger.error(f"Error deleting question: {str(e)}")
            db.session.rollback()
            return {'success': False, 'message': 'Failed to delete question'}, 500

    @staticmethod
    def reuse_exam(exam_id, teacher_id):
        """
        Re-use an approved exam after 3 years have passed since approval.
        Creates a new draft copy of the exam with all questions.
        """
        try:
            from datetime import timedelta

            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            # Must be approved
            if exam.admin_status != 'approved':
                return {
                    'success': False,
                    'message': 'Only approved exams can be re-used'
                }, 400

            # Must be owned by this teacher
            if exam.teacher_id != teacher_id:
                return {
                    'success': False,
                    'message': 'Unauthorized - You do not own this exam'
                }, 403

            # Must be at least 3 years since approval
            if not exam.reviewed_at:
                return {
                    'success': False,
                    'message': 'Exam approval date is not recorded; cannot verify the 3-year eligibility'
                }, 400

            three_years = timedelta(days=3 * 365)
            if datetime.utcnow() - exam.reviewed_at < three_years:
                eligible_date = exam.reviewed_at + three_years
                return {
                    'success': False,
                    'message': f'This exam is not yet eligible for re-use. It will be eligible on {eligible_date.strftime("%B %d, %Y")}.'
                }, 400

            # Copy the exam as a new draft
            current_year = datetime.utcnow().year
            new_exam = Exam(
                title=f"{exam.title} (Re-Use {current_year})",
                description=exam.description,
                module_id=exam.module_id,
                teacher_id=teacher_id,
                category_id=exam.category_id,
                duration_minutes=exam.duration_minutes,
                total_questions=exam.total_questions,
                passing_score=exam.passing_score,
                admin_status='draft',
                submitted_to_admin=False,
            )
            db.session.add(new_exam)
            db.session.flush()  # get new_exam.exam_id

            # Copy all questions
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            for q in questions:
                new_question = ExamQuestion(
                    exam_id=new_exam.exam_id,
                    question_text=q.question_text,
                    question_type=q.question_type,
                    difficulty_level=q.difficulty_level,
                    bloom_level=q.bloom_level,
                    topic=q.topic,
                    options=q.options,
                    correct_answer=q.correct_answer,
                    points=q.points,
                )
                db.session.add(new_question)

            # Set re-use tracking fields (graceful - column may not exist yet)
            try:
                new_exam.reused_from_exam_id = exam_id
                new_exam.reused_at = datetime.utcnow()
            except Exception:
                pass  # column not yet migrated in DB — proceed without tracking

            db.session.commit()

            logger.info(f"Exam {exam_id} re-used as new exam {new_exam.exam_id} by teacher {teacher_id}")

            return {
                'success': True,
                'message': f'Exam re-used successfully. A new draft "{new_exam.title}" has been created.',
                'exam': new_exam.to_dict()
            }, 201

        except Exception as e:
            logger.error(f"Error re-using exam: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return {'success': False, 'message': f'Failed to re-use exam: {str(e)}'}, 500

    @staticmethod
    def get_exam_categories():
        """
        Get all exam categories
        Frontend: CreateExam.jsx  
        URL: GET /api/exams/categories
        """
        try:
            from app.exam.models import ExamCategory
            
            logger.info("Fetching all exam categories")
            
            # Get all categories from database
            categories = ExamCategory.query.all()
            
            logger.info(f"Found {len(categories)} categories")
            
            return {
                'success': True,
                'categories': [category.to_dict() for category in categories],
                'total': len(categories)
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting exam categories: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get exam categories: {str(e)}'
            }, 500

    @staticmethod
    def submit_exam_answers(submission_data, authenticated_user_id):
        """
        Submit answers for an exam (Students taking the exam).

        SECURITY: ``authenticated_user_id`` MUST come from the JWT identity
        (``get_jwt_identity()``), never from the request body.  This prevents
        a malicious caller from submitting answers on behalf of another user.
        """
        try:
            schema = ExamSubmissionCreateSchema()
            validated_data = schema.load(submission_data)

            exam_id = validated_data['exam_id']
            answers = validated_data['answers']

            # SECURITY FIX: user_id from JWT, not request body
            user_id = int(authenticated_user_id)
            
            # Check if exam exists
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Create submission
            submission = ExamSubmission(
                exam_id=exam_id,
                user_id=user_id,
                start_time=datetime.utcnow(),
                submit_time=datetime.utcnow(),
                is_completed=True
            )
            db.session.add(submission)
            db.session.flush()
            
            # Save answers and calculate score
            total_points = 0
            earned_points = 0
            
            for answer_data in answers:
                question_id = answer_data['question_id']
                answer_text = answer_data.get('answer_text', '')
                
                # Get question to check correct answer
                question = ExamQuestion.query.get(question_id)
                if question:
                    if question.question_type == 'problem_solving':
                        from app.exam.math_solver import numeric_answers_match
                        is_correct = numeric_answers_match(answer_text, question.correct_answer, tolerance=0.01)
                        if not is_correct:
                            is_correct = answer_text.strip().lower() == question.correct_answer.strip().lower()
                    else:
                        is_correct = answer_text.strip().lower() == question.correct_answer.strip().lower()
                    points = question.points or 1
                    total_points += points
                    points_earned = points if is_correct else 0
                    earned_points += points_earned
                    
                    # Save answer
                    answer = ExamAnswer(
                        submission_id=submission.submission_id,
                        question_id=question_id,
                        answer_text=answer_text,
                        is_correct=is_correct,
                        points_earned=points_earned
                    )
                    db.session.add(answer)
            
            # Update submission with scores
            submission.total_points = total_points
            submission.score = earned_points
            
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Exam submitted successfully',
                'submission_id': submission.submission_id,
                'score': earned_points,
                'total_points': total_points
            }, 201
            
        except Exception as e:
            logger.error(f"Error submitting exam answers: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            db.session.rollback()
            return {
                'success': False,
                'message': f'Failed to submit exam: {str(e)}'
            }, 500

    @staticmethod
    def get_exam_submissions(exam_id, page=1, per_page=10):
        """Get paginated submissions for an exam"""
        try:
            query = ExamSubmission.query.filter_by(exam_id=exam_id)\
                .order_by(ExamSubmission.created_at.desc())
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)

            return {
                'success': True,
                'submissions': [s.to_dict() for s in paginated.items],
                'total': paginated.total,
                'page': page,
                'per_page': per_page,
                'total_pages': paginated.pages,
            }, 200

        except Exception as e:
            logger.error(f"Error getting exam submissions: {str(e)}")
            return {'success': False, 'message': 'Failed to get submissions'}, 500

    @staticmethod
    def get_user_submissions(user_id, page=1, per_page=10):
        """Get paginated exam submissions for a specific user"""
        try:
            query = ExamSubmission.query.filter_by(user_id=user_id)\
                .order_by(ExamSubmission.created_at.desc())
            paginated = query.paginate(page=page, per_page=per_page, error_out=False)

            return {
                'success': True,
                'submissions': [s.to_dict() for s in paginated.items],
                'total': paginated.total,
                'page': page,
                'per_page': per_page,
                'total_pages': paginated.pages,
            }, 200

        except Exception as e:
            logger.error(f"Error getting user submissions: {str(e)}")
            return {'success': False, 'message': 'Failed to get user submissions'}, 500

    @staticmethod
    def get_submission_details(submission_id):
        """Get detailed information about a specific submission including answers"""
        try:
            submission = ExamSubmission.query.get(submission_id)
            if not submission:
                return {'success': False, 'message': 'Submission not found'}, 404
            
            # Get answers for this submission
            answers = ExamAnswer.query.filter_by(submission_id=submission_id).all()
            
            submission_data = submission.to_dict()
            submission_data['answers'] = [answer.to_dict() for answer in answers]
            
            return {
                'success': True,
                'submission': submission_data
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting submission details: {str(e)}")
            return {'success': False, 'message': 'Failed to get submission details'}, 500

    @staticmethod
    def get_exam_tos(exam_id):
        """Generate Table of Specification for an exam"""
        try:
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404

            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            if not questions:
                return {
                    'success': False,
                    'message': 'No questions found for this exam'
                }, 404

            # Convert questions to format expected by TOS generator
            from app.exam.bloom_classifier import BloomClassifier

            questions_data = []
            for q in questions:
                q_dict = {
                    'question_text': q.question_text,
                    'question_type': q.question_type,
                    'difficulty_level': q.difficulty_level,
                    'points': q.points or 1,
                    'bloom_level': q.bloom_level or 'remembering',
                    'topic': q.topic or 'General'
                }
                questions_data.append(q_dict)

            # Only auto-classify if bloom_level was never set (None or empty string).
            # Never override a valid teacher-chosen level like 'remembering'.
            bloom_classifier = BloomClassifier()
            for q in questions_data:
                if not q.get('bloom_level'):
                    q['bloom_level'] = bloom_classifier.classify_question(q['question_text'])

            # Extract topics
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

            cognitive_levels = ['remembering', 'understanding', 'applying', 'analyzing', 'evaluating', 'creating']

            return {
                'success': True,
                'exam_id': exam_id,
                'exam_title': exam.title,
                'tos': tos,
                'total_questions': len(questions),
                'topics_count': len(topics),
                'cognitive_levels_count': len([k for k, v in tos.get('cognitive_distribution', {}).items() if v > 0]),
                'cognitive_levels': [
                    {
                        'level': level,
                        'count': tos.get('cognitive_distribution', {}).get(level, 0),
                        'percentage': tos.get('cognitive_percentages', {}).get(level, 0)
                    }
                    for level in cognitive_levels
                ],
                'topics': [
                    {
                        'name': topic,
                        'question_count': sum(tos.get('topic_cognitive_matrix', {}).get(topic, {}).values()),
                        'percentage': round(sum(tos.get('topic_cognitive_matrix', {}).get(topic, {}).values()) / len(questions) * 100, 1) if len(questions) > 0 else 0,
                        'difficulty': max(
                            tos.get('topic_difficulty_matrix', {}).get(topic, {'easy': 0, 'medium': 0, 'hard': 0}),
                            key=lambda d: tos.get('topic_difficulty_matrix', {}).get(topic, {}).get(d, 0),
                            default='medium'
                        )
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

        except Exception as e:
            logger.error(f"Error generating TOS: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to generate TOS: {str(e)}'
            }, 500

    @staticmethod
    def get_answer_key(exam_id):
        """
        Get answer key for an exam from exam_answers table
        Returns all questions with their correct answers
        """
        try:
            logger.info(f"Fetching answer key for exam {exam_id}")
            
            # Get exam
            exam = Exam.query.get(exam_id)
            if not exam:
                return {'success': False, 'message': 'Exam not found'}, 404
            
            # Get all questions for this exam
            questions = ExamQuestion.query.filter_by(exam_id=exam_id).all()
            
            if not questions:
                return {
                    'success': False,
                    'message': 'No questions found for this exam'
                }, 404
            
            logger.info(f"Found {len(questions)} questions for exam {exam_id}")
            
            # Get the submission with correct answers (teacher's submission)
            submission = ExamSubmission.query.filter_by(
                exam_id=exam_id,
                user_id=exam.teacher_id,
                is_completed=True
            ).first()
            
            # Build answer key data
            questions_data = []
            total_points = 0
            
            for question in questions:
                # Get the correct answer from exam_answers table
                correct_answer = question.correct_answer  # Default from question
                points = question.points or 1
                
                # If submission exists, get answer from exam_answers table
                if submission:
                    answer_record = ExamAnswer.query.filter_by(
                        submission_id=submission.submission_id,
                        question_id=question.question_id
                    ).first()
                    
                    if answer_record and answer_record.answer_text:
                        correct_answer = answer_record.answer_text
                        points = answer_record.points_earned or question.points or 1
                
                total_points += points
                
                question_data = {
                    'question_id': question.question_id,
                    'question_text': question.question_text,
                    'question_type': question.question_type,
                    'difficulty_level': question.difficulty_level,
                    'correct_answer': correct_answer,
                    'points': points
                }
                
                # Add options for multiple choice questions
                if question.options:
                    try:
                        if isinstance(question.options, str):
                            question_data['options'] = json.loads(question.options)
                        else:
                            question_data['options'] = question.options
                    except:
                        question_data['options'] = []
                
                questions_data.append(question_data)
            
            # Build response
            answer_key = {
                'exam_id': exam.exam_id,
                'title': exam.title,
                'description': exam.description or '',
                'subject_name': exam.module.subject.subject_name if exam.module and exam.module.subject else None,
                'category_name': exam.category.category_name if exam.category else None,
                'total_questions': len(questions),
                'total_points': total_points,
                'duration_minutes': exam.duration_minutes or 60,
                'teacher_name': f"{exam.teacher.first_name} {exam.teacher.last_name}" if exam.teacher else 'Unknown',
                'questions': questions_data
            }
            
            logger.info(f"Successfully generated answer key for exam {exam_id}")
            logger.info(f"Total questions: {len(questions)}, Total points: {total_points}")
            
            return {
                'success': True,
                'answer_key': answer_key
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting answer key: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get answer key: {str(e)}'
            }, 500
            
    
