from celery import Celery
from app.config import get_settings
settings = get_settings()
celery_app = Celery("reconiq", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_track_started=True, task_time_limit=900, task_soft_time_limit=840, worker_prefetch_multiplier=1)


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def health_job(self):
    return {"status": "ok", "task_id": self.request.id}
