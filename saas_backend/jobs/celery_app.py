from __future__ import annotations

from datetime import datetime

from celery import Celery

from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "clinical_saas",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
)

celery_app.autodiscover_tasks(["saas_backend.jobs.tasks"])

# Register beat schedules
from . import schedules  # noqa: E402, F401
