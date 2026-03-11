from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException

from app.auth.models import User
from app.utils.decorators import module_owner_or_admin
from app.utils.logger import get_logger
import os
import mimetypes

# File upload security
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'xlsx', 'txt',
                      'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}
ALLOWED_MIMES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    # Image types
    'image/jpeg', 'image/png', 'image/gif',
    'image/bmp', 'image/tiff', 'image/webp',
}

def _is_allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

module_bp = Blueprint("modules", __name__)

logger = get_logger(__name__)

# Roles allowed to archive/unarchive modules
ARCHIVE_ALLOWED_ROLES = {'department_head', 'admin', 'department'}


# =========================
# Upload Module
# =========================

@module_bp.route("/upload", methods=["POST", "OPTIONS"])
def upload_module():
    """Upload a new module"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        verify_jwt_in_request()

        # Check role
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        if user.role.lower() not in ['teacher', 'admin']:
            return jsonify({"success": False, "message": "Insufficient permissions"}), 403

        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file provided"}), 400

        file = request.files["file"]
        if not file or file.filename == "":
            return jsonify({"success": False, "message": "No file selected"}), 400

        # File type validation
        if not _is_allowed_file(file.filename):
            return jsonify({
                "success": False,
                "message": f"Invalid file type. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            }), 400

        mime_type, _ = mimetypes.guess_type(file.filename)
        if mime_type and mime_type not in ALLOWED_MIMES:
            return jsonify({
                "success": False,
                "message": "File content type is not permitted."
            }), 400

        subject_id = request.form.get("subject_id", type=int)
        teaching_hours = request.form.get("teaching_hours", type=int)

        if not subject_id:
            return jsonify({
                "success": False,
                "message": "subject_id is required"
            }), 400

        teacher_id = user_id

        logger.info(f"Module upload: teacher={teacher_id}, subject={subject_id}, file={file.filename}")

        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.save_module(
            file=file,
            teacher_id=teacher_id,
            subject_id=subject_id,
            teaching_hours=teaching_hours
        )

        return jsonify(result), status_code

    except JWTExtendedException:
        return jsonify({
            "success": False,
            "message": "Authentication failed"
        }), 401

    except Exception as e:
        logger.error(f"Upload module error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


# =========================
# Get Module Info
# =========================

@module_bp.route("/<int:module_id>", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module(module_id):
    """Get a specific module by ID (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_by_id(module_id)
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Get module error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/teacher/<int:teacher_id>", methods=["GET", "OPTIONS"])
@jwt_required()
def get_modules_by_teacher(teacher_id):
    """Get all modules for a specific teacher (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"success": False, "message": "User not found"}), 404

        # Authorization: own modules or admin
        if current_user_id != teacher_id and current_user.role.lower() != "admin":
            return jsonify({"success": False, "message": "Unauthorized access"}), 403

        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 10, type=int), 100)  # Cap at 100

        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_modules_by_teacher(
            teacher_id, page, per_page
        )

        return jsonify(result), status_code

    except JWTExtendedException:
        return jsonify({"success": False, "message": "Authentication failed"}), 401

    except Exception as e:
        logger.error(f"Error in get_modules_by_teacher: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


# =========================
# Module NLP / AI Outputs
# =========================

@module_bp.route("/<int:module_id>/content", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_content(module_id):
    """Get module content (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_content(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module content error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/<int:module_id>/summary", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_summary(module_id):
    """Get module summary (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_summary(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module summary error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/<int:module_id>/keywords", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_keywords(module_id):
    """Get module keywords (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_keywords(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module keywords error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/<int:module_id>/topics", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_topics(module_id):
    """Get module topics (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_topics(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module topics error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/<int:module_id>/entities", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_entities(module_id):
    """Get module entities (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_entities(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module entities error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


@module_bp.route("/<int:module_id>/questions", methods=["GET", "OPTIONS"])
@jwt_required()
@module_owner_or_admin
def get_module_questions(module_id):
    """Get module questions (ownership-checked)"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    try:
        from app.module_processor.saved_module import SavedModuleService
        result, status_code = SavedModuleService.get_module_questions(module_id)
        return jsonify(result), status_code
    except Exception as e:
        logger.error(f"Get module questions error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500


# =========================
# Download Module File
# =========================

@module_bp.route("/<int:module_id>/download", methods=["GET", "OPTIONS"])
def download_module(module_id):
    """Download module file"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        verify_jwt_in_request()

        from app.module_processor.models import Module
        module = Module.query.get(module_id)

        if not module:
            return jsonify({"success": False, "message": "Module not found"}), 404

        # Bug 2 fix: IDOR — only the owning teacher or an admin may download
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)

        if not current_user:
            return jsonify({"success": False, "message": "User not found"}), 404

        if module.teacher_id != current_user_id and current_user.role.lower() != 'admin':
            return jsonify({"success": False, "message": "Unauthorized: you do not own this module"}), 403

        # Bug 1 fix: guard for missing/deleted file + use basename instead of original_filename
        if not module.file_path or not os.path.exists(module.file_path):
            return jsonify({"success": False, "message": "File not found on server"}), 404

        return send_file(
            module.file_path,
            as_attachment=True,
            download_name=os.path.basename(module.file_path)
        )

    except JWTExtendedException as e:
        return jsonify({"success": False, "message": "Authentication failed"}), 401
    except Exception as e:
        logger.error(f"Download module error: {e}", exc_info=True)
        return jsonify({"success": False, "message": "An internal error occurred"}), 500

# =========================
# Archive Module (NEW)
# =========================

@module_bp.route("/<int:module_id>/archive", methods=["PUT", "OPTIONS"])
def archive_module(module_id):
    """Archive or unarchive a module"""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200
    
    try:
        verify_jwt_in_request()
        
        current_user_id = get_jwt_identity()
        current_user = User.query.get(int(current_user_id))
        
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Only department heads and admins can archive
        if current_user.role.lower() not in ARCHIVE_ALLOWED_ROLES:
            return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        # Get the module
        from app.module_processor.models import Module
        from app.database import db
        
        module = Module.query.get(module_id)
        if not module:
            return jsonify({'success': False, 'message': 'Module not found'}), 404
        
        # Get is_archived status from request
        data = request.get_json()
        is_archived = data.get('is_archived', False)
        
        # Update module
        module.is_archived = is_archived
        db.session.commit()
        
        action = 'archived' if is_archived else 'unarchived'
        
        logger.info(f"Module {module_id} {action} by user {current_user_id}")
        
        return jsonify({
            'success': True,
            'message': f'Module {action} successfully',
            'module': {
                'module_id': module.module_id,
                'title': module.title,
                'is_archived': module.is_archived
            }
        }), 200
        
    except JWTExtendedException as e:
        logger.error(f"JWT Error in archive_module: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401

    except Exception as e:
        from app.database import db
        db.session.rollback()
        logger.error(f"Archive module error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500


# =========================
# Module Images
# =========================

@module_bp.route("/<int:module_id>/images", methods=["GET", "OPTIONS"])
def get_module_images(module_id):
    """List all images extracted from a module document."""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        verify_jwt_in_request()

        from app.module_processor.models import Module, ModuleImage
        module = Module.query.get(module_id)
        if not module:
            return jsonify({'success': False, 'message': 'Module not found'}), 404

        # Ownership / admin / department-head check
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        role = (current_user.role or '').lower()
        privileged_roles = {'admin', 'department', 'department_head'}
        is_owner = module.teacher_id == current_user_id

        if not (is_owner or role in privileged_roles):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        images = ModuleImage.query.filter_by(module_id=module_id)\
            .order_by(ModuleImage.image_index).all()

        return jsonify({
            'success': True,
            'module_id': module_id,
            'images': [img.to_dict() for img in images],
            'total': len(images),
        }), 200

    except JWTExtendedException:
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401
    except Exception as e:
        logger.error(f"Get module images error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500


@module_bp.route("/<int:module_id>/images/<int:image_id>/file", methods=["GET", "OPTIONS"])
def serve_module_image(module_id, image_id):
    """
    Serve the raw image file for a specific module image.
    The browser / frontend can embed this URL in <img src="…">.
    """
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        verify_jwt_in_request()

        from app.module_processor.models import Module, ModuleImage
        module = Module.query.get(module_id)
        if not module:
            return jsonify({'success': False, 'message': 'Module not found'}), 404

        # Ownership / admin / department-head check
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        if not current_user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        role = (current_user.role or '').lower()
        privileged_roles = {'admin', 'department', 'department_head'}
        is_owner = module.teacher_id == current_user_id

        if not (is_owner or role in privileged_roles):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        img = ModuleImage.query.filter_by(image_id=image_id, module_id=module_id).first()
        if not img:
            return jsonify({'success': False, 'message': 'Image not found'}), 404

        # Resolve possible path variants (relative vs absolute; app/ prefix).
        # current_app.root_path = .../backend/app  (the package dir)
        # Uploads live at .../backend/uploads/...  (one level up)
        backend_dir = os.path.dirname(current_app.root_path)  # .../backend
        candidates = []
        if img.image_path:
            candidates.append(img.image_path)
            # Resolve relative path from backend root (where uploads/ lives)
            if not os.path.isabs(img.image_path):
                candidates.append(os.path.join(backend_dir, img.image_path))
                candidates.append(os.path.join(current_app.root_path, img.image_path))
            # If path mistakenly includes "/app/", try without it
            if f"{os.sep}app{os.sep}" in img.image_path:
                stripped = img.image_path.replace(f"{os.sep}app{os.sep}", os.sep)
                candidates.append(stripped)
                candidates.append(os.path.join(backend_dir, stripped))
            # Rebuild from known storage conventions:
            # - backend/uploads/module_images/<id>/
            # - backend/uploads/modules_images/<id>/ (legacy/alt naming)
            for root in (backend_dir, current_app.root_path):
                for folder_name in ('module_images', 'modules_images'):
                    base_dir = os.path.join(root, 'uploads', folder_name, str(module_id))
                    candidates.append(os.path.join(base_dir, os.path.basename(img.image_path)))

        chosen = next((p for p in candidates if p and os.path.exists(p)), None)
        if not chosen:
            logger.warning(f"Image file missing on disk for image_id={image_id}, module_id={module_id}, tried {len(candidates)} paths")
            return jsonify({'success': False, 'message': 'Image file not found on server'}), 404

        # CRITICAL: convert to absolute path — os.path.exists() checks from CWD
        # but Flask send_file() resolves relative paths from root_path (app/),
        # which is a different directory.  Using abspath() resolves from CWD
        # (where the file was actually found).
        chosen = os.path.abspath(chosen)

        import mimetypes
        from io import BytesIO
        mime, _ = mimetypes.guess_type(chosen)

        # Some DOC/DOCX extracted images are WMF/EMF; browsers usually can't render
        # those directly in <img>. Convert on-the-fly to PNG for reliable preview.
        try:
            from PIL import Image  # Pillow
            with Image.open(chosen) as pil_image:
                detected_format = str(pil_image.format or "").upper()
                file_ext = os.path.splitext(chosen)[1].lower()
                if detected_format in {"WMF", "EMF"} or file_ext in {".wmf", ".emf"}:
                    # Ask Pillow to render vector images at a readable DPI.
                    try:
                        pil_image.load(dpi=300)
                    except TypeError:
                        # Older Pillow builds may not accept keyword args.
                        pil_image.load()
                    except Exception:
                        pass

                    rendered = pil_image.convert("RGB")

                    # Many math WMF snippets render very small (e.g., ~100px wide).
                    # Upscale to a practical preview size while keeping aspect ratio.
                    width, height = rendered.size
                    if width > 0 and height > 0:
                        target_longest_side = 1400
                        current_longest_side = max(width, height)
                        scale = max(1.0, target_longest_side / float(current_longest_side))
                        if scale > 1.0:
                            try:
                                resampling = Image.Resampling.LANCZOS
                            except AttributeError:
                                resampling = Image.LANCZOS
                            rendered = rendered.resize(
                                (int(width * scale), int(height * scale)),
                                resampling,
                            )

                    converted = BytesIO()
                    rendered.save(converted, format="PNG", optimize=True)
                    converted.seek(0)
                    return send_file(converted, mimetype='image/png')
        except Exception as conversion_error:
            logger.debug(
                f"On-the-fly image conversion skipped for image_id={image_id}: {conversion_error}"
            )
            # If conversion fails, continue with original file response.
            pass

        try:
            return send_file(chosen, mimetype=mime or 'image/png')
        except (FileNotFoundError, OSError) as fe:
            logger.warning(f"Image file disappeared after exists-check for image_id={image_id}: {fe}")
            return jsonify({'success': False, 'message': 'Image file not found on server'}), 404

    except JWTExtendedException:
        return jsonify({'success': False, 'message': 'Authentication failed'}), 401
    except Exception as e:
        logger.error(f"Serve module image error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'An internal error occurred'}), 500
