from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

import pandas as pd
from sqlalchemy.orm import Session

from . import models


def aggregate_usage(subscription_id: int, db: Session) -> Dict[str, Any]:
    events = (
        db.query(models.UsageEvent)
        .filter(models.UsageEvent.subscription_id == subscription_id)
        .order_by(models.UsageEvent.created_at.asc())
        .all()
    )

    if not events:
        return {
            "total_events": 0,
            "total_tokens": 0,
            "daily_avg": 0.0,
            "total_cost_usd": 0.0,
        }

    rows = [
        {
            "event_type": event.event_type,
            "tokens": extract_tokens(event.payload),
            "cost_usd": event.cost_usd or 0.0,
            "created_at": event.created_at,
        }
        for event in events
    ]
    df = pd.DataFrame(rows)
    df["created_at"] = pd.to_datetime(df["created_at"])
    daily = df.set_index("created_at")["tokens"].resample("D").sum()

    return {
        "total_events": len(events),
        "total_tokens": int(df["tokens"].sum()),
        "daily_avg": float(daily.mean()) if not daily.empty else 0.0,
        "total_cost_usd": round(float(df["cost_usd"].sum()), 4),
    }


def extract_tokens(payload: str | None) -> int:
    if not payload:
        return 0
    try:
        data = json.loads(payload)
        if "total_tokens" in data:
            return int(data["total_tokens"])
        prompt = int(data.get("prompt_tokens", 0))
        completion = int(data.get("completion_tokens", 0))
        if prompt or completion:
            return prompt + completion
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return len(payload.split())


def generate_report(sub_id: int, db: Session, format: str = "csv") -> str:
    stats = aggregate_usage(sub_id, db)
    df = pd.DataFrame([stats])
    return df.to_csv(index=False) if format == "csv" else df.to_json(orient="records")


@contextmanager
def process_stream(data_gen: Generator) -> Generator[List[Any], None, None]:
    batch: list[Any] = []
    try:
        for item in data_gen:
            batch.append(item)
            if len(batch) >= 100:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        pass
