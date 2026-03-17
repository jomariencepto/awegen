import os
import json
import random
import re
import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, current_app, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity

# Import Exporters
from app.exports.pdf_exporter import PDFExporter
from app.exports.word_exporter import WordExporter
from app.exports.xlsx_exporter import XLSXExporter
from app.exports.report_exporter import ReportExporter 
from app.utils.exam_password import get_exam_download_password

# Import ReportLab for System Report PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from app.utils.decorators import role_required, admin_required
from app.utils.logger import get_logger
import traceback

logger = get_logger(__name__)
DOCX_ENCRYPTED_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# ==========================================
# BLUEPRINTS
# ==========================================

exports_bp = Blueprint('exports', __name__)
reports_bp = Blueprint('reports', __name__) # New Blueprint for Reports


def get_temp_path(filename):
    """Get absolute path for temp file"""
    # FIXED: Removed extra closing parenthesis
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    temp_dir = os.path.join(project_root, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, filename)


def parse_question_options(questions):
    """Parse question options from JSON string to list"""
    parsed_questions = []
    
    for question in questions:
        q = dict(question) if isinstance(question, dict) else question.__dict__
        
        if 'options' in q and q['options']:
            if isinstance(q['options'], str):
                try:
                    q['options'] = json.loads(q['options'])
                    logger.debug(f"Parsed options as JSON: {q['options']}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse options as JSON: {e}")
                    if ',' in q['options']:
                        q['options'] = [opt.strip() for opt in q['options'].split(',')]
                    else:
                        q['options'] = [q['options']]
            elif not isinstance(q['options'], list):
                q['options'] = [str(q['options'])]
        else:
            q['options'] = []
        
        parsed_questions.append(q)
    
    return parsed_questions


def _encrypt_pdf_if_needed(path):
    """Encrypt PDF with a static password if configured."""
    if not path.lower().endswith('.pdf'):
        return path, []
    pdf_password = get_exam_download_password()
    if not pdf_password:
        return path, []
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        logger.warning("PyPDF2 not installed; skipping PDF encryption.")
        return path, []

    try:
        reader = PdfReader(path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(pdf_password)
        enc_path = get_temp_path(f"enc_{os.path.basename(path)}")
        with open(enc_path, "wb") as f:
            writer.write(f)
        logger.info(f"Encrypted PDF generated at {enc_path}")
        return enc_path, [enc_path]
    except Exception as e:
        logger.error(f"Failed to encrypt PDF {path}: {e}")
        return path, []


def _protect_docx_with_msoffcrypto(path, doc_password, protected_path):
    """Protect DOCX using msoffcrypto-tool when available."""
    from msoffcrypto.format.ooxml import OOXMLFile

    with open(path, 'rb') as source_file, open(protected_path, 'wb') as target_file:
        OOXMLFile(source_file).encrypt(doc_password, target_file)


def _protect_docx_with_word_com(path, doc_password, protected_path):
    """Protect DOCX using Microsoft Word COM automation."""
    word_app = None
    document = None
    pythoncom_module = None
    com_initialized = False

    try:
        try:
            import pythoncom as _pythoncom
            pythoncom_module = _pythoncom
            pythoncom_module.CoInitialize()
            com_initialized = True
        except ImportError:
            pythoncom_module = None

        import win32com.client

        word_app = win32com.client.DispatchEx('Word.Application')
        word_app.Visible = False
        word_app.DisplayAlerts = 0

        document = word_app.Documents.Open(
            FileName=os.path.abspath(path),
            ConfirmConversions=False,
            ReadOnly=False,
            AddToRecentFiles=False,
            Visible=False,
            OpenAndRepair=False,
            NoEncodingDialog=True,
        )
        document.SaveAs2(
            FileName=os.path.abspath(protected_path),
            FileFormat=12,
            Password=doc_password,
            AddToRecentFiles=False,
            ReadOnlyRecommended=False,
        )
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word_app is not None:
            try:
                word_app.Quit()
            except Exception:
                pass
        if com_initialized and pythoncom_module is not None:
            try:
                pythoncom_module.CoUninitialize()
            except Exception:
                pass


def _is_password_protected_docx(path):
    """Return True when the DOCX is wrapped in Office password encryption."""
    try:
        with open(path, 'rb') as protected_file:
            return protected_file.read(len(DOCX_ENCRYPTED_MAGIC)) == DOCX_ENCRYPTED_MAGIC
    except OSError:
        return False


def _protect_docx_if_needed(path):
    """Protect DOCX with the configured download password when available."""
    if not path.lower().endswith('.docx'):
        return path, []

    doc_password = get_exam_download_password()
    if not doc_password:
        return path, []

    protected_path = get_temp_path(f"enc_{os.path.basename(path)}")

    try:
        try:
            _protect_docx_with_msoffcrypto(path, doc_password, protected_path)
            if os.path.exists(protected_path) and _is_password_protected_docx(protected_path):
                logger.info(
                    f"Password-protected DOCX generated at {protected_path} via msoffcrypto-tool"
                )
                return protected_path, [protected_path]
            logger.warning(
                "msoffcrypto-tool returned a DOCX without Office encryption; falling back to Word COM."
            )
        except ImportError:
            logger.info(
                "msoffcrypto-tool not available; falling back to Word COM for DOCX protection."
            )
        except Exception as msoffcrypto_error:
            logger.warning(
                f"msoffcrypto-tool failed for DOCX protection ({msoffcrypto_error}); "
                "falling back to Word COM."
            )
            try:
                if os.path.exists(protected_path):
                    os.remove(protected_path)
            except OSError:
                pass

        _protect_docx_with_word_com(path, doc_password, protected_path)
        if os.path.exists(protected_path) and _is_password_protected_docx(protected_path):
            logger.info(f"Password-protected DOCX generated at {protected_path} via Word COM")
            return protected_path, [protected_path]

        raise RuntimeError(
            "DOCX password protection is enabled, but the exported DOCX could not be encrypted."
        )
    except ImportError:
        logger.error(
            "DOCX password protection dependencies are unavailable; refusing to send an unprotected DOCX."
        )
        raise RuntimeError(
            "DOCX password protection is enabled, but the required DOCX encryption dependency is unavailable."
        )
    except Exception as e:
        logger.error(f"Failed to protect DOCX {path}: {e}", exc_info=True)
        try:
            if os.path.exists(protected_path):
                os.remove(protected_path)
        except OSError:
            pass
        raise RuntimeError(
            "DOCX password protection is enabled, but the exported DOCX could not be encrypted."
        ) from e


def _protect_download_if_needed(path):
    """Apply format-specific password protection before sending the file."""
    lowered = path.lower()
    if lowered.endswith('.pdf'):
        return _encrypt_pdf_if_needed(path)
    if lowered.endswith('.docx'):
        return _protect_docx_if_needed(path)
    return path, []


def _sanitize_filename(text):
    """Helper to create safe filenames using Python regex."""
    return re.sub(r'[^a-z0-9]', '_', str(text).lower())


def _prepare_exam_export_data(exam_id, shuffle=False):
    """Centralized helper to fetch and prepare exam data."""
    from app.exam.service import ExamService
    
    logger.info(f"Fetching exam {exam_id} from database... (Shuffle: {shuffle})")
    result, status_code = ExamService.get_exam_by_id(exam_id)
    
    if not result.get('success'):
        logger.warning(f"Exam {exam_id} not found or access denied")
        return None, status_code
    
    logger.info(f"Exam {exam_id} retrieved successfully")
    
    exam_data = result.get('exam', {})
    # FIX: Questions are nested inside exam_data, not at top level
    questions = exam_data.get('questions', [])
    
    questions = parse_question_options(questions)
    
    if shuffle:
        logger.info(f"Randomizing questions for Special Exam {exam_id}")
        random.shuffle(questions)
    
    export_data = {
        'title': exam_data.get('title', 'Untitled Exam'),
        'description': exam_data.get('description', ''),
        'teacher_name': exam_data.get('teacher_name'),
        'subject_name': exam_data.get('subject_name') or exam_data.get('module_title'),
        'category_name': exam_data.get('category_name'),
        'duration_minutes': exam_data.get('duration_minutes', 60),
        'total_questions': exam_data.get('total_questions', len(questions)),
        'passing_score': exam_data.get('passing_score', 0),
        'questions': questions
    }
    
    return export_data, 200


def _send_file_response(output_path, download_name, mimetype, inline=None):
    """Helper to send file and handle cleanup.
    
    inline: when True, return Content-Disposition inline (browser preview/print).
            If None, auto-detect via request.args.get('inline') == 'true'.
    """
    try:
        encrypted_path, extras = _protect_download_if_needed(output_path)
    except Exception:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError as cleanup_error:
            logger.warning(f"Could not delete temp file after protection failure: {cleanup_error}")
        raise

    # Infer inline flag if not provided
    if inline is None:
        try:
            inline = request.args.get('inline', 'false').lower() == 'true'
        except Exception:
            inline = False

    def cleanup():
        try:
            paths = {output_path, encrypted_path, *extras}
            for p in paths:
                if os.path.exists(p):
                    os.remove(p)
                    logger.info(f"Cleaned up temp file: {p}")
        except Exception as e:
            logger.warning(f"Could not delete temp files: {str(e)}")

    response = send_file(
        encrypted_path,
        as_attachment=not inline,
        download_name=download_name,
        mimetype=mimetype
    )
    
    response.call_on_close(cleanup)
    return response

# ==========================================
# EXAMS & TOS ROUTES (exports_bp)
# ==========================================

@exports_bp.route('/exam/<int:exam_id>/pdf', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_exam_pdf(exam_id):
    """Export exam to PDF format"""
    try:
        user_id = get_jwt_identity()
        logger.info(f"PDF export requested for exam {exam_id} by user {user_id}")

        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=False)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"exam_{exam_id}_{timestamp}.pdf"
        output_path = get_temp_path(filename)
        
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        pdf_exporter = PDFExporter()
        success = pdf_exporter.export_exam(export_data, output_path, include_header=include_header)
        
        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate PDF'}), 500
        
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(output_path, f"{safe_title}.pdf", 'application/pdf')

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_exam_pdf: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/word', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_exam_word(exam_id):
    """Export exam to Word format"""
    try:
        user_id = get_jwt_identity()
        logger.info(f"Word export requested for exam {exam_id} by user {user_id}")

        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=False)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"exam_{exam_id}_{timestamp}.docx"
        output_path = get_temp_path(filename)
        
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        word_exporter = WordExporter()
        success = word_exporter.export_exam(export_data, output_path, include_header=include_header)
        
        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate Word document'}), 500
        
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(
            output_path, 
            f"{safe_title}.docx", 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_exam_word: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/json', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_exam_json(exam_id):
    """Export exam to JSON format"""
    try:
        user_id = get_jwt_identity()
        logger.info(f"JSON export requested for exam {exam_id} by user {user_id}")

        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=False)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"exam_{exam_id}_{timestamp}.json"
        output_path = get_temp_path(filename)
        
        with open(output_path, 'w') as f:
            json.dump({**export_data, 'exported_at': datetime.now().isoformat()}, f, indent=2)
            
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(output_path, f"{safe_title}.json", 'application/json')

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_exam_json: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


# Special Exam Endpoints
@exports_bp.route('/exam/<int:exam_id>/special/pdf', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_exam_pdf(exam_id):
    """Export exam to PDF format with SHUFFLED questions"""
    try:
        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=True)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"special_exam_{exam_id}_{timestamp}.pdf"
        output_path = get_temp_path(filename)
        
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        pdf_exporter = PDFExporter()
        success = pdf_exporter.export_exam(export_data, output_path, include_header=include_header)
        
        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate Special PDF'}), 500
        
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(output_path, f"special_{safe_title}.pdf", 'application/pdf')

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_exam_pdf: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/special/word', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_exam_word(exam_id):
    """Export exam to Word format with SHUFFLED questions"""
    try:
        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=True)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"special_exam_{exam_id}_{timestamp}.docx"
        output_path = get_temp_path(filename)
        
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        word_exporter = WordExporter()
        success = word_exporter.export_exam(export_data, output_path, include_header=include_header)
        
        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate Special Word document'}), 500
        
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(
            output_path, 
            f"special_{safe_title}.docx", 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_exam_word: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/special/json', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_exam_json(exam_id):
    """Export exam to JSON format with SHUFFLED questions"""
    try:
        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=True)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"special_exam_{exam_id}_{timestamp}.json"
        output_path = get_temp_path(filename)
        
        with open(output_path, 'w') as f:
            json.dump({**export_data, 'exported_at': datetime.now().isoformat(), 'is_special': True}, f, indent=2)
            
        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(output_path, f"special_{safe_title}.json", 'application/json')

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_exam_json: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


# ==========================================
# XLSX EXPORT ROUTES
# ==========================================

@exports_bp.route('/exam/<int:exam_id>/xlsx', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_exam_xlsx(exam_id):
    """Export regular exam to XLSX format"""
    try:
        user_id = get_jwt_identity()
        logger.info(f"XLSX export requested for exam {exam_id} by user {user_id}")

        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=False)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = get_temp_path(f"exam_{exam_id}_{timestamp}.xlsx")
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        xlsx_exporter = XLSXExporter()
        success = xlsx_exporter.export_exam(export_data, output_path,
                                            include_header=include_header,
                                            is_special=False)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate XLSX'}), 500

        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(
            output_path, f"{safe_title}.xlsx",
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_exam_xlsx: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/special/xlsx', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_exam_xlsx(exam_id):
    """Export special (shuffled) exam to XLSX format"""
    try:
        export_data, status_code = _prepare_exam_export_data(exam_id, shuffle=True)
        if not export_data:
            return jsonify({'success': False, 'message': 'Exam not found'}), status_code

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = get_temp_path(f"special_exam_{exam_id}_{timestamp}.xlsx")
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        xlsx_exporter = XLSXExporter()
        success = xlsx_exporter.export_exam(export_data, output_path,
                                            include_header=include_header,
                                            is_special=True)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate Special XLSX'}), 500

        safe_title = _sanitize_filename(export_data['title'])
        return _send_file_response(
            output_path, f"special_{safe_title}.xlsx",
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_exam_xlsx: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@exports_bp.route('/exam/<int:exam_id>/answer-key/xlsx', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_answer_key_xlsx(exam_id):
    """Export answer key to XLSX format"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Answer key XLSX export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_answer_key(exam_id)
        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = get_temp_path(f"answer_key_{exam_id}_{timestamp}.xlsx")
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        xlsx_exporter = XLSXExporter()
        success = xlsx_exporter.export_answer_key(answer_key_data, output_path,
                                                   include_header=include_header,
                                                   is_special=False)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate answer key XLSX'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path, f"answer_key_{safe_title}.xlsx",
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_answer_key_xlsx: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


@exports_bp.route('/exam/<int:exam_id>/special-answer-key/xlsx', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_answer_key_xlsx(exam_id):
    """Export special (shuffled) answer key to XLSX format"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Special answer key XLSX export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_answer_key(exam_id)
        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']
        questions = answer_key_data['questions']
        random.shuffle(questions)
        answer_key_data['questions'] = questions

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = get_temp_path(f"special_answer_key_{exam_id}_{timestamp}.xlsx")
        include_header = request.args.get('include_header', 'true').lower() != 'false'

        xlsx_exporter = XLSXExporter()
        success = xlsx_exporter.export_answer_key(answer_key_data, output_path,
                                                   include_header=include_header,
                                                   is_special=True)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate special answer key XLSX'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path, f"special_answer_key_{safe_title}.xlsx",
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_answer_key_xlsx: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


# TOS Endpoints
@exports_bp.route('/tos/<int:exam_id>/pdf', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_tos_pdf(exam_id):
    """Export Table of Specifications to PDF format"""
    try:
        user_id = get_jwt_identity()
        from app.exam.service import ExamService
        
        result, status_code = ExamService.get_exam_by_id(exam_id)
        if not result.get('success'):
            return jsonify(result), status_code
        
        exam_data = result.get('exam', {})
        # FIX: Questions are nested inside exam_data
        questions = parse_question_options(exam_data.get('questions', []))
        
        cognitive_distribution = {}
        difficulty_distribution = {}
        topic_cognitive_matrix = {}
        
        for question in questions:
            cognitive_level = question.get('cognitive_level', 'remembering').lower()
            cognitive_distribution[cognitive_level] = cognitive_distribution.get(cognitive_level, 0) + 1
            difficulty = question.get('difficulty', 'medium').lower()
            difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
            topic = question.get('topic', 'General')
            if topic not in topic_cognitive_matrix:
                topic_cognitive_matrix[topic] = {}
            topic_cognitive_matrix[topic][cognitive_level] = topic_cognitive_matrix[topic].get(cognitive_level, 0) + 1
        
        total_questions = len(questions)
        cognitive_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in cognitive_distribution.items()
        }
        difficulty_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in difficulty_distribution.items()
        }
        
        tos_data = {
            'exam_title': exam_data.get('title', 'Untitled Exam'),
            'total_questions': total_questions,
            'duration_minutes': exam_data.get('duration_minutes', 60),
            'cognitive_distribution': cognitive_distribution,
            'cognitive_percentages': cognitive_percentages,
            'difficulty_distribution': difficulty_distribution,
            'difficulty_percentages': difficulty_percentages,
            'topic_cognitive_matrix': topic_cognitive_matrix
        }
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"tos_{exam_id}_{timestamp}.pdf"
        output_path = get_temp_path(filename)
        
        pdf_exporter = PDFExporter()
        success = pdf_exporter.export_tos(tos_data, output_path)
        
        if not success:
            return jsonify({'success': False, 'message': 'Failed to generate PDF'}), 500
        
        return _send_file_response(output_path, f"tos_{exam_id}.pdf", 'application/pdf')
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_tos_pdf: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/tos/<int:exam_id>/word', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_tos_word(exam_id):
    """Export Table of Specifications to Word format"""
    try:
        user_id = get_jwt_identity()
        from app.exam.service import ExamService
        
        result, status_code = ExamService.get_exam_by_id(exam_id)
        if not result.get('success'):
            return jsonify(result), status_code
        
        exam_data = result.get('exam', {})
        # FIX: Questions are nested inside exam_data
        questions = parse_question_options(exam_data.get('questions', []))
        
        cognitive_distribution = {}
        difficulty_distribution = {}
        topic_cognitive_matrix = {}
        
        for question in questions:
            cognitive_level = question.get('cognitive_level', 'remembering').lower()
            cognitive_distribution[cognitive_level] = cognitive_distribution.get(cognitive_level, 0) + 1
            difficulty = question.get('difficulty', 'medium').lower()
            difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
            topic = question.get('topic', 'General')
            if topic not in topic_cognitive_matrix:
                topic_cognitive_matrix[topic] = {}
            topic_cognitive_matrix[topic][cognitive_level] = topic_cognitive_matrix[topic].get(cognitive_level, 0) + 1
        
        total_questions = len(questions)
        cognitive_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in cognitive_distribution.items()
        }
        difficulty_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in difficulty_distribution.items()
        }
        
        tos_data = {
            'exam_title': exam_data.get('title', 'Untitled Exam'),
            'total_questions': total_questions,
            'duration_minutes': exam_data.get('duration_minutes', 60),
            'cognitive_distribution': cognitive_distribution,
            'cognitive_percentages': cognitive_percentages,
            'difficulty_distribution': difficulty_distribution,
            'difficulty_percentages': difficulty_percentages,
            'topic_cognitive_matrix': topic_cognitive_matrix
        }
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"tos_{exam_id}_{timestamp}.docx"
        output_path = get_temp_path(filename)
        
        word_exporter = WordExporter()
        success = word_exporter.export_tos(tos_data, output_path)
        
        if not success:
            return jsonify({'success': False, 'message': 'Failed to generate Word document'}), 500
        
        return _send_file_response(
            output_path, 
            f"tos_{exam_id}.docx", 
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_tos_word: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


@exports_bp.route('/tos/<int:exam_id>/xlsx', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_tos_xlsx(exam_id):
    """Export Table of Specifications to XLSX format"""
    try:
        from app.exam.service import ExamService
        from app.exports.xlsx_exporter import XLSXExporter

        user_id = get_jwt_identity()
        logger.info(f"TOS XLSX export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_exam_by_id(exam_id)
        if not result.get('success'):
            return jsonify(result), status_code

        exam_data = result.get('exam', {})
        questions = parse_question_options(exam_data.get('questions', []))

        cognitive_distribution = {}
        difficulty_distribution = {}
        topic_cognitive_matrix = {}

        for question in questions:
            cognitive_level = question.get('cognitive_level', 'remembering').lower()
            cognitive_distribution[cognitive_level] = cognitive_distribution.get(cognitive_level, 0) + 1
            difficulty = question.get('difficulty', 'medium').lower()
            difficulty_distribution[difficulty] = difficulty_distribution.get(difficulty, 0) + 1
            topic = question.get('topic', 'General')
            if topic not in topic_cognitive_matrix:
                topic_cognitive_matrix[topic] = {}
            topic_cognitive_matrix[topic][cognitive_level] = topic_cognitive_matrix[topic].get(cognitive_level, 0) + 1

        total_questions = len(questions)
        cognitive_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in cognitive_distribution.items()
        }
        difficulty_percentages = {
            level: round((count / total_questions * 100), 2) if total_questions > 0 else 0
            for level, count in difficulty_distribution.items()
        }

        tos_data = {
            'exam_title': exam_data.get('title', 'Untitled Exam'),
            'total_questions': total_questions,
            'duration_minutes': exam_data.get('duration_minutes', 60),
            'cognitive_distribution': cognitive_distribution,
            'cognitive_percentages': cognitive_percentages,
            'difficulty_distribution': difficulty_distribution,
            'difficulty_percentages': difficulty_percentages,
            'topic_cognitive_matrix': topic_cognitive_matrix
        }

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        output_path = get_temp_path(f"tos_{exam_id}_{timestamp}.xlsx")

        xlsx_exporter = XLSXExporter()
        success = xlsx_exporter.export_tos(tos_data, output_path)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate TOS XLSX'}), 500

        return _send_file_response(
            output_path, f"tos_{exam_id}.xlsx",
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_tos_xlsx: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error'}), 500


# ==========================================
# ANSWER KEY EXPORT ROUTES
# ==========================================

@exports_bp.route('/exam/<int:exam_id>/answer-key/pdf', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_answer_key_pdf(exam_id):
    """Export exam answer key to PDF format"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Answer key PDF export requested for exam {exam_id} by user {user_id}")

        # Get answer key data from service
        result, status_code = ExamService.get_answer_key(exam_id)

        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']

        # Create PDF using PDFExporter
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"answer_key_{exam_id}_{timestamp}.pdf"
        output_path = get_temp_path(filename)

        pdf_exporter = PDFExporter()
        include_header = request.args.get('include_header', 'true').lower() != 'false'
        success = pdf_exporter.export_answer_key(answer_key_data, output_path, include_header=include_header)

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate answer key PDF'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path,
            f'answer_key_{safe_title}.pdf',
            'application/pdf'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_answer_key_pdf: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


@exports_bp.route('/exam/<int:exam_id>/answer-key/word', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_answer_key_word(exam_id):
    """Export exam answer key to Word format"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Answer key DOCX export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_answer_key(exam_id)

        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"answer_key_{exam_id}_{timestamp}.docx"
        output_path = get_temp_path(filename)

        word_exporter = WordExporter()
        include_header = request.args.get('include_header', 'true').lower() != 'false'
        success = word_exporter.export_answer_key(
            answer_key_data, output_path, include_header=include_header
        )

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate answer key DOCX'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path,
            f'answer_key_{safe_title}.docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_answer_key_word: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


@exports_bp.route('/test', methods=['GET'])
def test_exports():
    """Test endpoint to verify exports are working"""
    return jsonify({
        'success': True,
        'message': 'Exports blueprint is working!',
        'available_formats': ['pdf', 'word', 'json', 'special_pdf', 'special_word', 'special_json']
    }), 200
    
@exports_bp.route('/exam/<int:exam_id>/special-answer-key/pdf', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_answer_key_pdf(exam_id):
    """Export exam answer key to PDF format with SHUFFLED questions"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Special answer key PDF export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_answer_key(exam_id)

        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']

        # SHUFFLE the questions for special answer key
        questions = answer_key_data['questions']
        random.shuffle(questions)
        answer_key_data['questions'] = questions

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"special_answer_key_{exam_id}_{timestamp}.pdf"
        output_path = get_temp_path(filename)

        pdf_exporter = PDFExporter()
        include_header = request.args.get('include_header', 'true').lower() != 'false'
        success = pdf_exporter.export_answer_key(
            answer_key_data, output_path, include_header=include_header
        )

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate special answer key PDF'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path,
            f'special_answer_key_{safe_title}.pdf',
            'application/pdf'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_answer_key_pdf: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


@exports_bp.route('/exam/<int:exam_id>/special-answer-key/word', methods=['GET'])
@jwt_required()
@role_required(['teacher', 'admin', 'department_head', 'department'])
def export_special_answer_key_word(exam_id):
    """Export exam answer key to Word format with SHUFFLED questions"""
    try:
        from app.exam.service import ExamService

        user_id = get_jwt_identity()
        logger.info(f"Special answer key DOCX export requested for exam {exam_id} by user {user_id}")

        result, status_code = ExamService.get_answer_key(exam_id)

        if not result.get('success'):
            return jsonify(result), status_code

        answer_key_data = result['answer_key']

        # SHUFFLE the questions for special answer key
        questions = answer_key_data['questions']
        random.shuffle(questions)
        answer_key_data['questions'] = questions

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"special_answer_key_{exam_id}_{timestamp}.docx"
        output_path = get_temp_path(filename)

        word_exporter = WordExporter()
        include_header = request.args.get('include_header', 'true').lower() != 'false'
        success = word_exporter.export_answer_key(
            answer_key_data, output_path, include_header=include_header
        )

        if not success or not os.path.exists(output_path):
            return jsonify({'success': False, 'message': 'Failed to generate special answer key Word document'}), 500

        safe_title = _sanitize_filename(answer_key_data['title'])
        return _send_file_response(
            output_path,
            f'special_answer_key_{safe_title}.docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    except Exception as e:
        logger.error(f"CRITICAL ERROR in export_special_answer_key_word: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'Internal server error: {str(e)}'}), 500


# ==========================================
# SYSTEM REPORTS ROUTES (reports_bp)
# ==========================================


def _get_date_range(range_type):
    """Helper to calculate start and end dates"""
    now = datetime.utcnow()
    if range_type == 'week':
        start_date = now - timedelta(days=7)
    elif range_type == 'month':
        start_date = now - timedelta(days=30)
    elif range_type == 'quarter':
        start_date = now - timedelta(days=90)
    elif range_type == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)
    return start_date, now

# Helper function to get exam status counts robustly
def _get_exam_status_counts():
    from app.exam.models import Exam
    
    total_exams = Exam.query.count()

    # Highest priority: admin_status workflow (draft/pending/approved/...)
    if hasattr(Exam, 'admin_status'):
        approved_exams = Exam.query.filter(Exam.admin_status == 'approved').count()
        pending_exams = Exam.query.filter(Exam.admin_status != 'approved').count()
        return total_exams, approved_exams, pending_exams

    # Fallbacks for older schemas
    if hasattr(Exam, 'status'):
        approved_exams = Exam.query.filter(Exam.status == 'approved').count()
        pending_exams = Exam.query.filter(Exam.status != 'approved').count()
        return total_exams, approved_exams, pending_exams

    if hasattr(Exam, 'exam_status'):
        approved_exams = Exam.query.filter(Exam.exam_status == 'approved').count()
        pending_exams = Exam.query.filter(Exam.exam_status != 'approved').count()
        return total_exams, approved_exams, pending_exams

    if hasattr(Exam, 'is_approved'):
        approved_exams = Exam.query.filter(Exam.is_approved == True).count()
        pending_exams = Exam.query.filter(Exam.is_approved != True).count()
        return total_exams, approved_exams, pending_exams

    if hasattr(Exam, 'is_active'):
        approved_exams = Exam.query.filter(Exam.is_active == True).count()
        pending_exams = Exam.query.filter(Exam.is_active != True).count()
        return total_exams, approved_exams, pending_exams

    # Default: if no status fields exist, treat all as approved
    logger.info("Exam model has no status flags; defaulting all exams as approved for reports.")
    return total_exams, total_exams, 0


@reports_bp.route('/system', methods=['GET'])
@jwt_required()
@admin_required
def get_system_report():
    """Fetch system overview data matching Frontend requirements"""
    try:
        from app.auth.models import User
        from app.exam.models import Exam
        # Import Module if exists, otherwise 0
        try:
            from app.module_processor.models import Module
            HasModule = True
        except ImportError:
            HasModule = False

        report_type = request.args.get('type', 'overview')
        time_range = request.args.get('range', 'month')
        
        logger.info(f"Fetching system report: type={report_type}, range={time_range}")
        
        # 1. User Statistics
        total_users = User.query.count()
        new_users = User.query.filter(User.created_at >= _get_date_range(time_range)[0]).count() if hasattr(User, 'created_at') else 0
        
        # 2. Exam Statistics (Using robust helper)
        total_exams, approved_exams, pending_exams = _get_exam_status_counts()
        
        # 3. Module Statistics
        total_modules = Module.query.count() if HasModule else 0

        stats = {
            'totalUsers': total_users,
            'totalExams': total_exams,
            'approvedExams': approved_exams,
            'pendingExams': pending_exams,
            'totalModules': total_modules,
            'newUsers': new_users
        }

        return jsonify({
            'success': True,
            'stats': stats,
            'meta': {
                'type': report_type,
                'range': time_range
            }
        }), 200

    except Exception as e:
        logger.error(f"Error generating system report: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to generate report'
        }), 500


@reports_bp.route('/export/<format>', methods=['GET'])
@jwt_required()
@admin_required
def export_report(format):
    """Export system report to PDF or CSV"""
    try:
        from app.auth.models import User
        from app.exam.models import Exam
        
        # Import Module if exists
        try:
            from app.module_processor.models import Module
            HasModule = True
        except ImportError:
            HasModule = False

        time_range = request.args.get('range', 'month')
        start_date, end_date = _get_date_range(time_range)
        
        total_users = User.query.count()
        
        # Exam Statistics (Using robust helper)
        total_exams, approved_exams, pending_exams = _get_exam_status_counts()
        
        total_modules = Module.query.count() if HasModule else 0

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"system_report_{timestamp}.{format}"

        if format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            writer.writerow(['Metric', 'Count'])
            writer.writerow(['Total Users', total_users])
            writer.writerow(['Total Exams', total_exams])
            writer.writerow(['Approved Exams', approved_exams])
            writer.writerow(['Pending Exams', pending_exams])
            writer.writerow(['Total Modules', total_modules])
            writer.writerow(['Report Generated At', datetime.now().isoformat()])
            
            output.seek(0)
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = f"attachment; filename={filename}"
            response.headers["Content-type"] = "text/csv"
            return response

        elif format == 'pdf':
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            elements.append(Paragraph("System Report", styles['Title']))
            elements.append(Paragraph(f"Range: {time_range}", styles['Normal']))
            elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
            elements.append(Paragraph("<br/><br/>", styles['Normal']))

            data = [
                ['Metric', 'Value'],
                ['Total Users', str(total_users)],
                ['Total Exams', str(total_exams)],
                ['Approved Exams', str(approved_exams)],
                ['Pending Exams', str(pending_exams)],
                ['Total Modules', str(total_modules)]
            ]
            
            table = Table(data, colWidths=[200, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(table)

            doc.build(elements)
            buffer.seek(0)
            
            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf'
            )

        else:
            return jsonify({'success': False, 'message': 'Invalid format'}), 400

    except Exception as e:
        logger.error(f"Error exporting report: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Export failed'}), 500
