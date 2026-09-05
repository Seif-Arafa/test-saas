from __future__ import annotations

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..data_pipeline import extract_tokens
from ..schemas import DocumentStats, RagStats, UsageStats


def get_usage_stats(db: Session, subscription_id: int) -> UsageStats:
    events = (
        db.query(models.UsageEvent)
        .filter(models.UsageEvent.subscription_id == subscription_id)
        .order_by(models.UsageEvent.created_at.asc())
        .all()
    )

    daily_tokens: dict[str, int] = {}
    by_event_type: dict[str, int] = {}
    total_tokens = 0
    total_cost = 0.0

    for event in events:
        tokens = extract_tokens(event.payload)
        total_tokens += tokens
        total_cost += event.cost_usd or 0.0
        day = event.created_at.strftime("%Y-%m-%d")
        daily_tokens[day] = daily_tokens.get(day, 0) + tokens
        by_event_type[event.event_type] = by_event_type.get(event.event_type, 0) + 1

    return UsageStats(
        total_events=len(events),
        total_tokens=total_tokens,
        daily_tokens=daily_tokens,
        total_cost_usd=round(total_cost, 4),
        by_event_type=by_event_type,
    )


def get_document_stats(db: Session, org_id: int) -> DocumentStats:
    documents = db.query(models.Document).filter(models.Document.org_id == org_id).all()
    by_status: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    total_storage = 0

    for doc in documents:
        by_status[doc.status] = by_status.get(doc.status, 0) + 1
        by_doc_type[doc.doc_type] = by_doc_type.get(doc.doc_type, 0) + 1
        total_storage += doc.file_size_bytes

    return DocumentStats(
        total_documents=len(documents),
        by_status=by_status,
        by_doc_type=by_doc_type,
        total_storage_bytes=total_storage,
    )


def get_rag_stats(db: Session, org_id: int) -> RagStats:
    events = (
        db.query(models.UsageEvent)
        .filter(
            models.UsageEvent.org_id == org_id,
            models.UsageEvent.event_type == "clinical_rag_chat",
        )
        .all()
    )
    if not events:
        return RagStats(total_queries=0, avg_latency_ms=0.0, avg_citations_per_query=0.0)

    latencies: list[float] = []
    citations: list[int] = []
    for event in events:
        if not event.payload:
            continue
        try:
            data = json.loads(event.payload)
            latencies.append(float(data.get("latency_ms", 0)))
            citations.append(int(data.get("citation_count", 0)))
        except json.JSONDecodeError:
            continue

    return RagStats(
        total_queries=len(events),
        avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        avg_citations_per_query=round(sum(citations) / len(citations), 2) if citations else 0.0,
    )


def list_jobs(db: Session, org_id: int, limit: int = 50) -> list[models.Job]:
    return (
        db.query(models.Job)
        .filter(models.Job.org_id == org_id)
        .order_by(models.Job.created_at.desc())
        .limit(limit)
        .all()
    )
