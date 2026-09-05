from __future__ import annotations

from celery.schedules import crontab

from .celery_app import celery_app

celery_app.conf.beat_schedule = {
    "nightly-usage-report": {
        "task": "saas_backend.jobs.tasks.nightly_usage_report_task",
        "schedule": crontab(hour=2, minute=0),
    },
}
