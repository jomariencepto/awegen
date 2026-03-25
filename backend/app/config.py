import os
from datetime import timedelta


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Secrets — MUST be overridden via environment variables in production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-dev-only")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-dev-only-jwt")

    # MySQL database (required) - XAMPP default has no password #App password dvhl wmkg mbzy lppt

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root@localhost/awegen_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,       # detect stale connections
        'pool_recycle': 1800,         # recycle connections every 30 min
        'pool_size': 10,
        'max_overflow': 20,
    }

    # JWT expiration:
    # - Set JWT_DISABLE_EXPIRATION=true to disable token expiration entirely.
    # - Otherwise use env-configurable durations.
    JWT_DISABLE_EXPIRATION = _env_bool("JWT_DISABLE_EXPIRATION", False)
    if JWT_DISABLE_EXPIRATION:
        JWT_ACCESS_TOKEN_EXPIRES = False
        JWT_REFRESH_TOKEN_EXPIRES = False
    else:
        JWT_ACCESS_TOKEN_EXPIRES = timedelta(
            hours=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "1"))
        )
        JWT_REFRESH_TOKEN_EXPIRES = timedelta(
            days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))
        )

    # Cookie-based JWT settings (httpOnly, secure in production)
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = False          # overridden in ProductionConfig
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_REFRESH_COOKIE_NAME = "refresh_token_cookie"
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-TOKEN"

    # File uploads
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # NLP paths
    NLP_MODEL_PATH = os.environ.get("NLP_MODEL_PATH", "models/nlp")
    MAX_KEYWORDS = 20
    MIN_KEYWORD_FREQUENCY = 2

    # Exam generator
    DEFAULT_EXAM_DURATION = 60
    DEFAULT_PASSING_SCORE = 75

    # Pagination
    ITEMS_PER_PAGE = 10

    # Background queue (RQ / Celery)
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True          # only send cookies over HTTPS
    JWT_COOKIE_SAMESITE = "Strict"
    PROPAGATE_EXCEPTIONS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

    def __init__(self):
        super().__init__()
        # Enforce non-default secrets in production
        if self.SECRET_KEY.startswith("change-me"):
            raise RuntimeError(
                "SECRET_KEY must be set via environment variable in production"
            )
        if self.JWT_SECRET_KEY.startswith("change-me"):
            raise RuntimeError(
                "JWT_SECRET_KEY must be set via environment variable in production"
            )


class TestingConfig(Config):
    TESTING = True
    # SECURITY FIX: use a dedicated test database — never the live DB
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "mysql+pymysql://root@localhost/awegen_test_db"
    )
    JWT_COOKIE_CSRF_PROTECT = False   # simplify test requests


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig
}
