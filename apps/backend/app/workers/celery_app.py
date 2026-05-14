from celery import Celery

from app.config.settings import get_settings

settings = get_settings()
celery_app = Celery("case_ai", broker=settings.redis_url, backend=settings.redis_url)

