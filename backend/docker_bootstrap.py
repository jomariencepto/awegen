import os
import sys
import time

from sqlalchemy import create_engine, inspect, text


def wait_for_database():
    database_url = os.getenv("DATABASE_URL")
    retries = int(os.getenv("DB_CONNECT_RETRIES", "40"))
    delay_seconds = int(os.getenv("DB_CONNECT_DELAY", "3"))

    if not database_url:
        print("DATABASE_URL is not set.")
        return False

    for attempt in range(1, retries + 1):
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database is ready.")
            return True
        except Exception as exc:
            print(f"Waiting for database ({attempt}/{retries}): {exc}")
            time.sleep(delay_seconds)

    print("Database connection timed out.")
    return False


def initialize_tables():
    from app import create_app
    from app.database import db

    flask_env = os.getenv("FLASK_ENV", "development")
    app = create_app(flask_env)
    with app.app_context():
        db.create_all()
        try:
            inspector = inspect(db.engine)
            exam_question_columns = {col["name"] for col in inspector.get_columns("exam_questions")}
            if "section_instruction" not in exam_question_columns:
                db.session.execute(
                    text(
                        "ALTER TABLE exam_questions "
                        "ADD COLUMN section_instruction TEXT NULL AFTER question_text"
                    )
                )
                db.session.commit()
                print("Added missing exam_questions.section_instruction column.")
        except Exception as exc:
            db.session.rollback()
            print(f"Warning: failed to ensure exam_questions.section_instruction column: {exc}")
    print("Database tables initialized (create_all).")


if __name__ == "__main__":
    if not wait_for_database():
        sys.exit(1)

    initialize_tables()
