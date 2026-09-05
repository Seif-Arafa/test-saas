from __future__ import annotations

from datetime import datetime

from .celery_app import celery_app


@celery_app.task(name="saas_backend.jobs.tasks.ingest_document_task", bind=True, max_retries=2)
def ingest_document_task(self, document_id: int, job_id: int) -> dict:
    from ..database import db_session
    from .. import models
    from ..ingestion.service import ingest_document_record

    with db_session() as db:
        job = db.query(models.Job).filter(models.Job.id == job_id).first()
        if job:
            job.status = "running"
            db.commit()

        try:
            result = ingest_document_record(db, document_id)
            if job:
                job.status = "done"
                job.result = result
                job.completed_at = datetime.utcnow()
                db.commit()
            return result
        except Exception as exc:
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.utcnow()
                db.commit()
            raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="saas_backend.jobs.tasks.nightly_usage_report_task")
def nightly_usage_report_task() -> dict:
    from ..database import db_session
    from .. import models
    from ..data_pipeline import aggregate_usage

    summaries = []
    with db_session() as db:
        subscriptions = db.query(models.Subscription).filter(models.Subscription.status == "active").all()
        for sub in subscriptions:
            stats = aggregate_usage(sub.id, db)
            summaries.append({"subscription_id": sub.id, **stats})
    return {"generated_at": datetime.utcnow().isoformat(), "subscriptions": summaries}


def enqueue_ingest_document(document_id: int, job_id: int) -> str | None:
    result = ingest_document_task.delay(document_id, job_id)
    return result.id
