from __future__ import annotations

import os
import re
import unicodedata

from sqlalchemy.orm import Session

from .. import models

DEFAULT_PLANS = [
    {
        "name": "free",
        "display_name": "Free",
        "max_tokens_daily": 5_000,
        "max_tokens_monthly": 50_000,
        "max_documents": 10,
        "max_storage_mb": 100,
        "allowed_models": ["gpt-4o-mini"],
        "features": {"rag": True, "batch_jobs": False, "api_sync": False},
        "price_cents": 0,
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "max_tokens_daily": 50_000,
        "max_tokens_monthly": 500_000,
        "max_documents": 500,
        "max_storage_mb": 5_120,
        "allowed_models": ["gpt-4o-mini", "gpt-4o"],
        "features": {"rag": True, "batch_jobs": True, "api_sync": False},
        "price_cents": 9900,
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise",
        "max_tokens_daily": 500_000,
        "max_tokens_monthly": 5_000_000,
        "max_documents": 10_000,
        "max_storage_mb": 51_200,
        "allowed_models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        "features": {"rag": True, "batch_jobs": True, "api_sync": True},
        "price_cents": 49900,
    },
]


def seed_plans(db: Session) -> None:
    for plan_data in DEFAULT_PLANS:
        existing = db.query(models.Plan).filter(models.Plan.name == plan_data["name"]).first()
        if existing:
            continue
        db.add(models.Plan(**plan_data))
    db.commit()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-") or "org"
