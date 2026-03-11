from celery import Celery
from app.module_processor.saved_module import SavedModuleService
from app import create_app

celery = Celery('tasks', broker='redis://localhost:6379/0')
# Celery 6.0 changes broker retry behavior; keep retries on startup to avoid warnings.
celery.conf.update(broker_connection_retry_on_startup=True)

# create flask app
flask_app = create_app()


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_module_content(self, module_id):

    with flask_app.app_context():
        try:
            return SavedModuleService.process_module_content(module_id)

        except Exception as exc:
            raise self.retry(exc=exc)
