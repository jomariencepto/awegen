import os
from pathlib import Path

from dotenv import dotenv_values, set_key
from flask import current_app, has_app_context

from app.utils.logger import get_logger

logger = get_logger(__name__)

EXAM_PASSWORD_ENV_KEY = "PDF_DOWNLOAD_PASSWORD"


def _backend_root() -> Path:
    # backend/app/utils/exam_password.py -> backend/
    return Path(__file__).resolve().parents[2]


def _env_file_path() -> Path:
    configured = os.environ.get("ENV_FILE_PATH")
    if configured:
        return Path(configured)
    return _backend_root() / ".env"


def get_exam_download_password() -> str:
    runtime_value = os.environ.get(EXAM_PASSWORD_ENV_KEY)
    if runtime_value is not None:
        return str(runtime_value).strip()

    env_file = _env_file_path()
    if env_file.exists():
        values = dotenv_values(env_file)
        file_value = values.get(EXAM_PASSWORD_ENV_KEY)
        if file_value is not None:
            resolved = str(file_value).strip()
            os.environ[EXAM_PASSWORD_ENV_KEY] = resolved
            if has_app_context():
                current_app.config[EXAM_PASSWORD_ENV_KEY] = resolved
            return resolved

    return ""


def set_exam_download_password(password: str) -> None:
    normalized = (password or "").strip()
    env_file = _env_file_path()
    env_file.parent.mkdir(parents=True, exist_ok=True)
    if not env_file.exists():
        env_file.touch()

    set_key(str(env_file), EXAM_PASSWORD_ENV_KEY, normalized, quote_mode="always")

    os.environ[EXAM_PASSWORD_ENV_KEY] = normalized
    if has_app_context():
        current_app.config[EXAM_PASSWORD_ENV_KEY] = normalized

    logger.info("Exam download password updated in .env configuration.")
