from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.department.service import DepartmentService
from app.utils.decorators import role_required
from app.auth.models import User
from app.exam.models import Exam, ExamQuestion  # ⭐ ADD THIS IMPORT
from app.utils.logger import get_logger  # ⭐ ADD THIS IMPORT
import json  # ⭐ ADD THIS IMPORT

logger = get_logger(__name__)  # ⭐ ADD THIS

department_bp = Blueprint('departments', __name__)


# =========================
# NEW: Get All Departments
# =========================

@department_bp.route('', methods=['GET'])
@jwt_required()
def get_all_departments():
    """Get all departments - needed for SavedExams.jsx dropdown"""
    try:
        result, status_code = DepartmentService.get_all_departments()
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to fetch departments: {str(e)}'
        }), 500


# =========================
# Department-specific endpoints
# =========================

@department_bp.route('/<int:department_id>/dashboard', methods=['GET'])
@jwt_required()
@role_required(['department', 'admin'])
def get_department_dashboard(department_id):
    current_user_id = get_jwt_identity()
    
    current_user = User.query.get(int(current_user_id))
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if current_user.role != 'admin' and current_user.department_id != department_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    result, status_code = DepartmentService.get_department_dashboard(department_id)
    return jsonify(result), status_code


@department_bp.route('/<int:department_id>/exams', methods=['GET'])
@jwt_required()
@role_required(['department', 'admin'])
def get_department_exams(department_id):
    current_user_id = get_jwt_identity()
    
    current_user = User.query.get(int(current_user_id))
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if current_user.role != 'admin' and current_user.department_id != department_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = DepartmentService.get_department_exams(department_id, status, page, per_page)
    return jsonify(result), status_code


@department_bp.route('/<int:department_id>/teachers', methods=['GET'])
@jwt_required()
@role_required(['department', 'admin'])
def get_department_teachers_by_id(department_id):
    current_user_id = get_jwt_identity()
    
    current_user = User.query.get(int(current_user_id))
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if current_user.role != 'admin' and current_user.department_id != department_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = DepartmentService.get_department_teachers(department_id, page, per_page)
    return jsonify(result), status_code


@department_bp.route('/<int:department_id>/subjects', methods=['GET'])
@jwt_required()
@role_required(['department', 'admin'])
def get_department_subjects_by_id(department_id):
    current_user_id = get_jwt_identity()
    
    current_user = User.query.get(int(current_user_id))
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
        
    if current_user.role != 'admin' and current_user.department_id != department_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    result, status_code = DepartmentService.get_department_subjects(department_id)
    return jsonify(result), status_code


# =========================
# Current User's Department Endpoints
# =========================

@department_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_my_department_dashboard():
    """Get dashboard for current user's department"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    logger.debug(f"User {current_user.email} has role: {current_user.role} and department_id: {current_user.department_id}")

    if current_user.role not in ['department', 'admin']:
        logger.warning(f"User {current_user.email} does not have required role. Current role: {current_user.role}")
        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403

    if not current_user.department_id:
        logger.warning(f"User {current_user.email} is not assigned to a department")
        return jsonify({'success': False, 'message': 'User not assigned to a department'}), 400
    
    result, status_code = DepartmentService.get_department_dashboard(current_user.department_id)
    return jsonify(result), status_code


@department_bp.route('/exams', methods=['GET'])
@jwt_required()
def get_my_department_exams():
    """Get exams for current user's department"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    
    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if current_user.role not in ['department', 'admin']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
    
    if not current_user.department_id:
        return jsonify({'success': False, 'message': 'User not assigned to a department'}), 400
    
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = DepartmentService.get_department_exams(
        current_user.department_id, status, page, per_page
    )
    return jsonify(result), status_code


@department_bp.route('/exams', methods=['POST'])
@jwt_required()
@role_required(['department', 'department_head', 'admin'])
def create_department_exam():
    """
    Create an exam as a department head. The exam is auto-approved on save.
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400

        creator_id = int(get_jwt_identity())
        result, status_code = DepartmentService.create_exam_for_department(data, creator_id)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Error creating department exam: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Failed to create exam: {str(e)}'
        }), 500


@department_bp.route('/teachers', methods=['GET'])
@jwt_required()
def get_my_department_teachers():
    """Get teachers for current user's department"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))

    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if current_user.role not in ['department', 'admin']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
    
    if not current_user.department_id:
        return jsonify({'success': False, 'message': 'User not assigned to a department'}), 400
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    result, status_code = DepartmentService.get_department_teachers(
        current_user.department_id, page, per_page
    )
    return jsonify(result), status_code


@department_bp.route('/subjects', methods=['GET'])
@jwt_required()
def get_my_department_subjects():
    """Get subjects for current user's department"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))

    if not current_user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    if current_user.role not in ['department', 'admin']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
    
    if not current_user.department_id:
        return jsonify({'success': False, 'message': 'User not assigned to a department'}), 400
    
    result, status_code = DepartmentService.get_department_subjects(current_user.department_id)
    return jsonify(result), status_code


# =====================================================
# ✅ NEW: Modules Bank - Get All Modules for Department
# =====================================================

@department_bp.route('/modules', methods=['GET'])
@jwt_required()
def get_department_modules():
    """
    Get all modules for current user's department
    Frontend: ModulesBank.jsx
    URL: GET /api/departments/modules
    """
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(int(current_user_id))
        
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if current_user.role not in ['department', 'admin']:
            return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        if not current_user.department_id:
            return jsonify({'success': False, 'message': 'User not assigned to a department'}), 400
        
        result, status_code = DepartmentService.get_department_modules(current_user.department_id)
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get modules: {str(e)}'
        }), 500


# =========================
# Exam Approval
# =========================

@department_bp.route('/exams/<int:exam_id>/approve', methods=['PUT'])
@jwt_required()
def approve_department_exam(exam_id):
    """
    Approve, reject, or request revision for an exam
    Accepts:
      - action (approve/reject/revision_required)
      - feedback (optional)
      - question_reviews (required when action=revision_required)
    """
    data = request.get_json()
    approver_id = get_jwt_identity()
    
    approver = User.query.get(int(approver_id))
    
    if not approver:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    if approver.role not in ['department', 'admin']:
        return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
    
    result, status_code = DepartmentService.approve_department_exam(exam_id, data, approver_id)
    return jsonify(result), status_code


# =====================================================
# ⭐ UPDATED: Exam Preview with Correct Answers
# =====================================================

@department_bp.route('/exams/<int:exam_id>/preview', methods=['GET'])
@jwt_required()
def get_exam_preview(exam_id):
    """
    ⭐ UPDATED: Get full exam preview with questions AND CORRECT ANSWERS
    Accessible by department users for reviewing exams.
    Frontend: ExamReview.jsx
    URL: GET /api/departments/exams/{exam_id}/preview
    """
    try:
        logger.info(f"📋 Department preview request for exam {exam_id}")
        
        current_user_id = get_jwt_identity()
        current_user = User.query.get(int(current_user_id))
        
        if not current_user:
            logger.error(f"❌ User {current_user_id} not found")
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if current_user.role not in ['department', 'admin']:
            logger.error(f"❌ User {current_user_id} has insufficient permissions")
            return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        # Get exam
        exam = Exam.query.get(exam_id)
        if not exam:
            logger.error(f"❌ Exam {exam_id} not found")
            return jsonify({'success': False, 'message': 'Exam not found'}), 404
        
        # ⭐ FIXED: Better department access logic
        # Admins can see all exams
        if current_user.role != 'admin':
            # Department heads need to verify access
            if current_user.department_id:
                # Check if exam belongs to department OR was sent to department
                exam_department_id = exam.department_id if hasattr(exam, 'department_id') else None
                sent_to_department = exam.sent_to_department if hasattr(exam, 'sent_to_department') else False
                
                logger.info(f"🔍 Access check: user_dept={current_user.department_id}, exam_dept={exam_department_id}, sent_to_dept={sent_to_department}")
                
                # Allow access if:
                # 1. Exam's department matches user's department
                # 2. Exam was sent to this department  
                # 3. Exam has no department (legacy exams)
                has_access = (
                    exam_department_id == current_user.department_id or
                    sent_to_department or
                    exam_department_id is None
                )
                
                if not has_access:
                    logger.error(f"❌ Unauthorized: Exam {exam_id} not accessible to department {current_user.department_id}")
                    return jsonify({
                        'success': False, 
                        'message': 'Unauthorized - Exam not in your department'
                    }), 403
                else:
                    logger.info(f"✅ Access granted for exam {exam_id}")
            else:
                logger.error(f"❌ User {current_user_id} has no department assigned")
                return jsonify({'success': False, 'message': 'User not assigned to a department'}), 403
        else:
            logger.info(f"✅ Admin access granted for exam {exam_id}")
        
        # Get questions WITH CORRECT ANSWERS
        questions = ExamQuestion.query.filter_by(exam_id=exam_id).order_by(ExamQuestion.question_id).all()
        
        logger.info(f"✅ Found {len(questions)} questions for exam {exam_id}")
        
        # Format questions with correct answers
        formatted_questions = []
        for q in questions:
            question_dict = {
                'question_id': q.question_id,
                'question_text': q.question_text,
                'question_type': q.question_type,
                'difficulty_level': q.difficulty_level,
                'correct_answer': q.correct_answer,  # ⭐ CRITICAL: Include correct answer!
                'points': q.points or 1,
                'feedback': q.feedback if hasattr(q, 'feedback') else None,
                # Include image linkage so Department preview can render teacher-attached images.
                'image_id': q.image_id,
                'image_module_id': q.image.module_id if getattr(q, 'image', None) else None,
            }
            
            # Add cognitive level if available
            if hasattr(q, 'cognitive_level') and q.cognitive_level:
                question_dict['cognitive_level'] = q.cognitive_level
            elif hasattr(q, 'bloom_level') and q.bloom_level:
                question_dict['cognitive_level'] = q.bloom_level
            else:
                question_dict['cognitive_level'] = None
            
            # Parse options if JSON string
            if q.options:
                try:
                    if isinstance(q.options, str):
                        question_dict['options'] = json.loads(q.options)
                    else:
                        question_dict['options'] = q.options
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse options for question {q.question_id}: {str(e)}")
                    question_dict['options'] = []
            else:
                question_dict['options'] = []
            
            formatted_questions.append(question_dict)
        
        # Get teacher info
        teacher = None
        teacher_name = "Unknown"
        if hasattr(exam, 'teacher_id') and exam.teacher_id:
            teacher = User.query.get(exam.teacher_id)
            if teacher and hasattr(teacher, 'first_name') and hasattr(teacher, 'last_name'):
                teacher_name = f"{teacher.first_name} {teacher.last_name}"
        
        # Build exam response
        exam_data = {
            'exam_id': exam.exam_id,
            'title': exam.title,
            'description': exam.description if hasattr(exam, 'description') else None,
            'duration_minutes': exam.duration_minutes if hasattr(exam, 'duration_minutes') else 60,
            'passing_score': exam.passing_score if hasattr(exam, 'passing_score') else 75,
            'total_questions': len(formatted_questions),
            'teacher_name': teacher_name,
            'teacher_id': exam.teacher_id if hasattr(exam, 'teacher_id') else None,
            'admin_status': exam.admin_status if hasattr(exam, 'admin_status') else 'draft',
            'submitted_at': exam.submitted_at.isoformat() if hasattr(exam, 'submitted_at') and exam.submitted_at else None,
            'instructor_notes': exam.instructor_notes if hasattr(exam, 'instructor_notes') else None
        }
        
        logger.info(f"✅ Returning exam preview with {len(formatted_questions)} questions WITH ANSWERS")
        
        return jsonify({
            'success': True,
            'exam': exam_data,
            'questions': formatted_questions
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error in get_exam_preview: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Failed to get exam preview: {str(e)}'
        }), 500


# ================================================================
# 📝 NEW ROUTE: Save Question Feedback
# Added after get_exam_preview route
# ================================================================
@department_bp.route('/exams/<int:exam_id>/questions/<int:question_id>/feedback', methods=['PUT'])
@jwt_required()
def save_question_feedback(exam_id, question_id):
    """
    Save per-question feedback for department review
    Frontend: ExamReview.jsx
    URL: PUT /api/departments/exams/{exam_id}/questions/{question_id}/feedback
    Body: { "feedback": "Your feedback here" }
    """
    try:
        logger.info(f"📝 Saving feedback for question {question_id} in exam {exam_id}")
        
        current_user_id = get_jwt_identity()
        current_user = User.query.get(int(current_user_id))
        
        if not current_user:
            logger.error(f"❌ User {current_user_id} not found")
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if current_user.role not in ['department', 'admin']:
            logger.error(f"❌ User {current_user_id} has insufficient permissions")
            return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        # Get request data
        data = request.get_json()
        feedback = data.get('feedback', '').strip()
        
        # Get question
        question = ExamQuestion.query.get(question_id)
        if not question:
            logger.error(f"❌ Question {question_id} not found")
            return jsonify({'success': False, 'message': 'Question not found'}), 404
        
        # Verify question belongs to exam
        if question.exam_id != exam_id:
            logger.error(f"❌ Question {question_id} does not belong to exam {exam_id}")
            return jsonify({'success': False, 'message': 'Question does not belong to this exam'}), 400

        exam = Exam.query.get(exam_id)
        if not exam:
            return jsonify({'success': False, 'message': 'Exam not found'}), 404

        if exam.admin_status in ['approved', 'rejected', 'revision_required'] and not exam.sent_to_department:
            return jsonify({
                'success': False,
                'message': 'Feedback already submitted for this review cycle and can no longer be edited.'
            }), 409
        
        # Update feedback
        question.feedback = feedback if feedback else None
        
        from app.database import db
        db.session.commit()
        
        feedback_action = 'saved' if feedback else 'cleared'
        logger.info(f"✅ Feedback {feedback_action} for question {question_id}")
        
        return jsonify({
            'success': True,
            'message': f'Feedback {feedback_action} successfully',
            'question_id': question_id,
            'feedback': feedback
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error saving feedback: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        from app.database import db
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Failed to save feedback: {str(e)}'
        }), 500


# =====================================================
# TOS (Table of Specification) for Department Users
# =====================================================

@department_bp.route('/exams/<int:exam_id>/tos', methods=['GET'])
@jwt_required()
def get_exam_tos(exam_id):
    """
    Get TOS (Table of Specification) data for an exam.
    Accessible by department users for reviewing exams.
    Frontend: ExamReview.jsx
    URL: GET /api/departments/exams/{exam_id}/tos
    """
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(int(current_user_id))
        
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if current_user.role not in ['department', 'admin']:
            return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        result, status_code = DepartmentService.get_exam_tos(exam_id)
        return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to get TOS: {str(e)}'
        }), 500


# =========================
# Management Endpoints (for frontend compatibility)
# =========================

@department_bp.route('/users/department/teachers', methods=['GET'])
@jwt_required()
def get_management_teachers():
    """
    Fetch teachers for the current user's department.
    Frontend: ManageUsers.jsx
    URL: /api/departments/users/department/teachers
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    
    if not current_user or not current_user.department_id:
        return jsonify({'success': False, 'message': 'Unauthorized or no department assigned'}), 403

    # Allow pagination parameters; default to a generous page size to surface all teachers
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get('per_page', 1000))
    except (TypeError, ValueError):
        per_page = 1000

    result, status_code = DepartmentService.get_department_teachers(
        current_user.department_id, 
        page=page, 
        per_page=per_page
    )
    
    if status_code == 200:
        return jsonify({
            'users': result.get('teachers', []),
            'total': result.get('total', 0),
            'pages': result.get('pages', 1),
            'current_page': result.get('current_page', 1)
        }), 200
    
    return jsonify(result), status_code


@department_bp.route('/subjects/department', methods=['GET'])
@jwt_required()
def get_upload_subjects():
    """
    Fetch subjects for the current user's department.
    Frontend: UploadModule.jsx
    URL: /api/departments/subjects/department
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    
    if not current_user or not current_user.department_id:
        return jsonify({'success': False, 'message': 'Unauthorized or no department assigned'}), 403
        
    result, status_code = DepartmentService.get_department_subjects(current_user.department_id)
    
    if status_code == 200:
        return jsonify({'subjects': result.get('subjects', [])}), 200
        
    return jsonify(result), status_code


@department_bp.route('/exams/department/all', methods=['GET'])
@jwt_required()
def get_all_department_exams():
    """
    Fetch ALL exams for TOS Reports.
    Frontend: TOSReports.jsx
    URL: /api/departments/exams/department/all
    """
    current_user_id = get_jwt_identity()
    current_user = User.query.get(int(current_user_id))
    
    if not current_user or not current_user.department_id:
        return jsonify({'success': False, 'message': 'Unauthorized or no department assigned'}), 403

    result, status_code = DepartmentService.get_department_exams(
        current_user.department_id, 
        status=None, 
        page=1, 
        per_page=1000 
    )
    
    if status_code == 200:
        return jsonify({'exams': result.get('exams', [])}), 200
        
    return jsonify(result), status_code
