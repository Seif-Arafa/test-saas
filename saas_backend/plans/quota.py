from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


def get_plan_for_subscription(db: Session, subscription: models.Subscription) -> models.Plan | None:
    if subscription.plan_id:
        return db.query(models.Plan).filter(models.Plan.id == subscription.plan_id).first()
    if subscription.plan_name:
        return db.query(models.Plan).filter(models.Plan.name == subscription.plan_name).first()
    return db.query(models.Plan).filter(models.Plan.name == "free").first()


def get_active_subscription(db: Session, org_id: int) -> models.Subscription | None:
    return (
        db.query(models.Subscription)
        .filter(
            models.Subscription.org_id == org_id,
            models.Subscription.status == "active",
        )
        .order_by(models.Subscription.id.desc())
        .first()
    )


def count_tokens_since(db: Session, subscription_id: int, since: datetime) -> int:
    from ..data_pipeline import extract_tokens

    events = (
        db.query(models.UsageEvent)
        .filter(
            models.UsageEvent.subscription_id == subscription_id,
            models.UsageEvent.created_at >= since,
        )
        .all()
    )
    return sum(extract_tokens(e.payload) for e in events)


def count_documents(db: Session, org_id: int) -> int:
    return db.query(models.Document).filter(models.Document.org_id == org_id).count()


def total_storage_bytes(db: Session, org_id: int) -> int:
    from sqlalchemy import func

    result = (
        db.query(func.coalesce(func.sum(models.Document.file_size_bytes), 0))
        .filter(models.Document.org_id == org_id)
        .scalar()
    )
    return int(result or 0)


def enforce_chat_quota(db: Session, subscription: models.Subscription, plan: models.Plan) -> None:
    now = datetime.utcnow()
    daily_tokens = count_tokens_since(db, subscription.id, now - timedelta(days=1))
    monthly_tokens = count_tokens_since(db, subscription.id, now - timedelta(days=30))

    if daily_tokens >= plan.max_tokens_daily:
        raise HTTPException(status_code=429, detail="Daily token quota exceeded for your plan")
    if monthly_tokens >= plan.max_tokens_monthly:
        raise HTTPException(status_code=429, detail="Monthly token quota exceeded for your plan")


def enforce_document_quota(db: Session, org_id: int, plan: models.Plan, new_file_bytes: int) -> None:
    doc_count = count_documents(db, org_id)
    if doc_count >= plan.max_documents:
        raise HTTPException(status_code=429, detail="Document limit reached for your plan")

    current_bytes = total_storage_bytes(db, org_id)
    max_bytes = plan.max_storage_mb * 1024 * 1024
    if current_bytes + new_file_bytes > max_bytes:
        raise HTTPException(status_code=429, detail="Storage limit reached for your plan")


def resolve_model(plan: models.Plan, requested: str | None) -> str:
    allowed = plan.allowed_models or ["gpt-4o-mini"]
    if requested and requested in allowed:
        return requested
    return allowed[0]
