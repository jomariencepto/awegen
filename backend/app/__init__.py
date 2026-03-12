# ==============================================================================
# app/__init__.py - PRODUCTION-READY FLASK CONFIGURATION
# ==============================================================================

from dotenv import load_dotenv
load_dotenv()  # Load environment variables

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
from werkzeug.exceptions import RequestEntityTooLarge

from app.database import init_db
from app.config import config_by_name
from app.utils.logger import setup_logging

# ==========================================================================
# NLTK DATA BOOTSTRAP — download required resources once at import time
# ==========================================================================
import nltk as _nltk

_NLTK_RESOURCES = [
    ('tokenizers/punkt', 'punkt'),
    ('tokenizers/punkt_tab', 'punkt_tab'),
    ('taggers/averaged_perceptron_tagger_eng', 'averaged_perceptron_tagger_eng'),
    ('corpora/wordnet', 'wordnet'),
    ('corpora/omw-1.4', 'omw-1.4'),
    ('corpora/stopwords', 'stopwords'),
]

for _check_path, _pkg_name in _NLTK_RESOURCES:
    try:
        _nltk.data.find(_check_path)
    except (LookupError, OSError):
        _nltk.download(_pkg_name, quiet=True)


def create_app(config_name=None):
    """
    Flask application factory with best practices
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    app.url_map.strict_slashes = False

    # ==========================================================================
    # DATABASE INITIALIZATION
    # ==========================================================================
    init_db(app)

    # ==========================================================================
    # JWT CONFIGURATION
    # ==========================================================================
    # JWT settings are loaded from Config class (config.py).
    # Only override the secret here if not already set by config.
    if not app.config.get("JWT_SECRET_KEY"):
        app.config["JWT_SECRET_KEY"] = os.getenv(
            "JWT_SECRET_KEY", "CHANGE-THIS-IN-PRODUCTION-USE-STRONG-SECRET"
        )
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_DECODE_ALGORITHMS"] = ["HS256"]
    # Cookie + Header dual mode (set in config.py: JWT_TOKEN_LOCATION = ["headers", "cookies"])
    app.config["JWT_HEADER_NAME"] = "Authorization"
    app.config["JWT_HEADER_TYPE"] = "Bearer"
    app.config["JWT_ERROR_MESSAGE_KEY"] = "message"
    jwt_manager = JWTManager(app)

    # ==========================================================================
    # RATE LIMITING
    # ==========================================================================
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["10000 per day", "1000 per hour"],
        storage_uri="memory://"
    )
    app.limiter = limiter

    @limiter.request_filter
    def _exempt_high_frequency_endpoints():
        path = request.path
        return (
            (path.endswith('/file') and '/images/' in path)
            or (path.endswith('/status') and '/modules/' in path)
        )

    # ==========================================================================
    # EXEMPT OPTIONS FROM JWT
    # ==========================================================================
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            return '', 200

    def _jwt_error_response(message, error_code):
        if request.method == "OPTIONS":
            return '', 200
        return jsonify({"success": False, "message": message, "error": error_code}), 401

    jwt_manager.invalid_token_loader(lambda e: _jwt_error_response("Invalid token", str(e)))
    jwt_manager.expired_token_loader(lambda h, p: _jwt_error_response("Token has expired. Please login again.", "token_expired"))
    jwt_manager.unauthorized_loader(lambda e: _jwt_error_response("Authorization token is required", "authorization_required"))
    jwt_manager.revoked_token_loader(lambda h, p: _jwt_error_response("Token has been revoked", "token_revoked"))

    # ==========================================================================
    # CORS CONFIGURATION
    # ==========================================================================
    is_production = config_name == "production"
    if is_production:
        allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
    else:
        allowed_origins = [
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:5000", "http://127.0.0.1:5000",
            "http://localhost:5173", "http://127.0.0.1:5173",
            "http://192.168.100.19:3000",
        ]

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": allowed_origins,
                "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Requested-With", "Accept"],
                "expose_headers": ["Content-Type", "Authorization", "X-Total-Count"],
                "supports_credentials": True,
                "max_age": 3600
            }
        },
        send_wildcard=False,
        always_send=True,
        automatic_options=True
    )

    # ==========================================================================
    # DATABASE MODELS & AI HEALTHCHECK
    # ==========================================================================
    with app.app_context():
        from app.users.models import School, Department, Subject
        from app.auth.models import Role, User, RefreshToken, OTPVerification
        from app.notifications.models import Notification
        from app.exam import models as exam_models
        from app.approval import models as approval_models
        from app.module_processor import models as module_models

        # AI health check (non-blocking by default)
        ai_check_on_start = os.getenv("AI_HEALTHCHECK_ON_START", "false").lower() == "true"
        ai_check_strict = os.getenv("AI_HEALTHCHECK_STRICT", "false").lower() == "true"
        app.config["AI_HEALTH_STATUS"] = {"healthy": True, "error": None}
        if ai_check_on_start:
            try:
                from app.module_processor.saved_module import run_ai_healthcheck
                run_ai_healthcheck()
            except Exception as e:
                app.config["AI_HEALTH_STATUS"] = {"healthy": False, "error": str(e)}
                app.logger.critical(f"AI healthcheck failed at startup: {e}", exc_info=True)
                if ai_check_strict:
                    raise

    # ==========================================================================
    # BLUEPRINTS
    # ==========================================================================
    from app.auth.routes import auth_bp
    from app.users.routes import users_bp
    from app.exam.routes import exam_bp
    from app.module_processor.routes import module_bp
    from app.approval.routes import approval_bp
    from app.admin.routes import admin_bp
    from app.department.routes import department_bp
    from app.exports.routes import exports_bp, reports_bp
    from app.notifications.routes import notifications_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(exam_bp, url_prefix="/api/exams")
    app.register_blueprint(module_bp, url_prefix="/api/modules")
    app.register_blueprint(approval_bp, url_prefix="/api/approvals")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(department_bp, url_prefix="/api/departments")
    app.register_blueprint(exports_bp, url_prefix="/api/exports")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")

    # ==========================================================================
    # ERROR HANDLERS
    # ==========================================================================
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"success": False, "message": "Bad request", "error": str(error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "message": "Resource not found"}), 404

    @app.errorhandler(413)
    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(error):
        max_bytes = int(app.config.get("MAX_CONTENT_LENGTH") or 0)
        max_mb = max_bytes / (1024 * 1024) if max_bytes else None
        message = (
            f"File too large. Maximum upload size is {max_mb:.0f} MB."
            if max_mb else
            "File too large."
        )
        return jsonify({"success": False, "message": message}), 413

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        app.logger.error(f"Unhandled exception: {error}", exc_info=True)
        return jsonify({"success": False, "message": "An unexpected error occurred"}), 500

    # ======================================================================
    # SECURITY HEADERS
    # ======================================================================
    @app.after_request
    def set_security_headers(response):
        # Enforce HTTPS on clients (only meaningful when served via HTTPS)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains; preload"
        )
        # Prevent MIME sniffing
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        # Clickjacking protection
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        # Limit referrer leakage
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Restrict powerful features (tight by default; relax if needed)
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), autoplay=(), fullscreen=(self)"
        )
        return response

    # ==========================================================================
    # HEALTHCHECK ENDPOINTS
    # ==========================================================================
    @app.route('/')
    def home():
        return jsonify({'message': 'Exam Generation System API', 'status': 'running', 'version': '1.0.0'}), 200

    @app.route('/health')
    def health_check():
        return jsonify({'status': 'healthy', 'environment': config_name, 'version': '1.0.0'}), 200

    @app.route('/health/ai')
    def health_check_ai():
        status = app.config.get("AI_HEALTH_STATUS", {"healthy": True, "error": None})
        if status["healthy"]:
            return jsonify({'status': 'healthy', 'ai': status.get("results")}), 200
        else:
            return jsonify({'status': 'unhealthy', 'error': status["error"]}), 500

    # ==========================================================================
    # DEVELOPMENT DEBUG ENDPOINTS
    # ==========================================================================
    if not is_production:
        @app.route('/api/debug/notifications')
        def debug_notifications():
            return jsonify({'message': 'Notifications endpoint is working!', 'routes': [str(rule) for rule in app.url_map.iter_rules() if 'notifications' in str(rule)]})

        @app.route('/api/cors-test')
        def cors_test():
            return jsonify({'message': 'CORS is working!', 'origin': allowed_origins, 'methods': ['GET','POST','PUT','DELETE','PATCH','OPTIONS']}), 200

    # ==========================================================================
    # ======================================================================
    # SECURITY HEADERS
    # ======================================================================
    @app.after_request
    def set_security_headers(response):
        # Referrer info leakage control
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Enforce HTTPS on clients (only meaningful when site is served via HTTPS)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Clickjacking protection (allow iframes only from same origin)
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        # Fine-grained feature controls — adjust if you need any of these
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), autoplay=(), fullscreen=(self)"
        )
        return response

    # Final security headers (override to ensure presence)
    @app.after_request
    def enforce_security_headers(response):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), autoplay=(), fullscreen=(self)"
        return response


    # PRINT REGISTERED ROUTES (Development only)
    # ==========================================================================
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" and not is_production:
        print_registered_routes(app)

    return app


def print_registered_routes(app):
    """Log all registered routes for debugging (dev only)."""
    import logging
    _logger = logging.getLogger(__name__)
    _logger.debug("=" * 80)
    _logger.debug("REGISTERED ROUTES:")
    _logger.debug("=" * 80)
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        _logger.debug(f"{methods:<20} {rule.rule}")
    _logger.debug("=" * 80)
