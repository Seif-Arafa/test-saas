from __future__ import annotations

import json
from typing import Any, Dict, List

import openai
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from . import models
from .analytics.usage import estimate_cost_usd
from .data_pipeline import aggregate_usage
from .plans.quota import enforce_chat_quota, get_plan_for_subscription, resolve_model


class AIEngine:
    """Subscription-aware OpenAI inference service."""

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required to use the AI Engine")
        self.client = openai.OpenAI(api_key=settings.openai_api_key)

    def chat_completion(
        self,
        subscription_id: int,
        messages: List[Dict[str, str]],
        max_tokens: int = 100,
        model: str | None = None,
    ) -> Dict[str, Any]:
        sub = (
            self.db.query(models.Subscription)
            .filter(models.Subscription.id == subscription_id)
            .first()
        )
        if not sub or sub.status != "active":
            raise HTTPException(status_code=403, detail="Invalid or inactive subscription")

        plan = get_plan_for_subscription(self.db, sub)
        if not plan:
            raise HTTPException(status_code=403, detail="Plan not found")

        enforce_chat_quota(self.db, sub, plan)
        resolved_model = resolve_model(plan, model)

        result = self.chat_completion_raw(
            messages=messages,
            max_tokens=max_tokens,
            model=resolved_model,
        )

        usage = result["usage"]
        cost = estimate_cost_usd(resolved_model, usage["prompt_tokens"], usage["completion_tokens"])
        event = models.UsageEvent(
            subscription_id=subscription_id,
            org_id=sub.org_id,
            event_type="chat_completion",
            resource_type="chat",
            payload=json.dumps(
                {
                    "model": resolved_model,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "messages": messages,
                }
            ),
            cost_usd=cost,
        )
        self.db.add(event)
        self.db.commit()
        return result

    def chat_completion_raw(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 100,
        model: str = "gpt-4o-mini",
    ) -> Dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI service error: {exc}") from exc

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else prompt_tokens + completion_tokens

        return {
            "id": response.id,
            "model": response.model,
            "choices": [
                {
                    "message": {
                        "role": response.choices[0].message.role,
                        "content": response.choices[0].message.content,
                    },
                    "finish_reason": response.choices[0].finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }


def get_ai_engine(db: Session = Depends(get_db)) -> AIEngine:
    return AIEngine(db)
