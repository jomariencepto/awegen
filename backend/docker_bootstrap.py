import os
import sys
import time

from sqlalchemy import create_engine, text


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
    print("Database tables initialized (create_all).")


if __name__ == "__main__":
    if not wait_for_database():
        sys.exit(1)

    initialize_tables()
