from __future__ import annotations

import json
import time
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..ai_engine import AIEngine
from ..analytics.usage import estimate_cost_usd
from ..plans.quota import enforce_chat_quota, get_active_subscription, get_plan_for_subscription, resolve_model
from ..rag.retriever import CLINICAL_DISCLAIMER, SYSTEM_PROMPT, build_context, retrieve_chunks


def clinical_chat(
    db: Session,
    *,
    org_id: int,
    user_id: int,
    payload: schemas.ClinicalChatRequest,
) -> schemas.ClinicalChatResponse:
    subscription = get_active_subscription(db, org_id)
    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription for this organization")

    plan = get_plan_for_subscription(db, subscription)
    if not plan:
        raise HTTPException(status_code=403, detail="Plan not found")

    enforce_chat_quota(db, subscription, plan)
    model = resolve_model(plan, payload.model)

    user_message = payload.messages[-1].content if payload.messages else ""
    if not user_message.strip():
        raise HTTPException(status_code=400, detail="Last message must be from the user")

    started = time.perf_counter()
    retrieved = retrieve_chunks(
        db,
        org_id,
        user_message,
        doc_types=payload.doc_types,
        specialty=payload.specialty,
    )
    context = build_context(retrieved)

    prompt_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Clinical context:\n{context}\n\n"
                f"Clinician question:\n{user_message}"
            ),
        },
    ]

    engine = AIEngine(db)
    result = engine.chat_completion_raw(
        messages=prompt_messages,
        max_tokens=payload.max_tokens or 500,
        model=model,
    )

    latency_ms = (time.perf_counter() - started) * 1000
    citations = [
        schemas.Citation(
            document_id=document.id,
            document_title=document.title,
            chunk_id=chunk.id,
            snippet=chunk.content[:300],
            page=(chunk.metadata_json or {}).get("page"),
        )
        for chunk, document, _ in retrieved
    ]

    conversation = _get_or_create_conversation(db, org_id, user_id, subscription.id, payload.conversation_id, user_message)
    db.add(
        models.ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
        )
    )
    db.add(
        models.ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result["choices"][0]["message"]["content"],
            citations_json=[c.model_dump() for c in citations],
        )
    )

    usage = result["usage"]
    cost = estimate_cost_usd(model, usage["prompt_tokens"], usage["completion_tokens"])
    db.add(
        models.UsageEvent(
            subscription_id=subscription.id,
            org_id=org_id,
            event_type="clinical_rag_chat",
            resource_type="chat",
            payload=json.dumps(
                {
                    "model": model,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "latency_ms": latency_ms,
                    "citation_count": len(citations),
                }
            ),
            cost_usd=cost,
        )
    )
    db.commit()

    return schemas.ClinicalChatResponse(
        conversation_id=conversation.id,
        answer=result["choices"][0]["message"]["content"],
        citations=citations,
        disclaimer=CLINICAL_DISCLAIMER,
        model=model,
        usage=usage,
    )


def _get_or_create_conversation(
    db: Session,
    org_id: int,
    user_id: int,
    subscription_id: int,
    conversation_id: int | None,
    first_message: str,
) -> models.Conversation:
    if conversation_id:
        conversation = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.id == conversation_id,
                models.Conversation.org_id == org_id,
                models.Conversation.user_id == user_id,
            )
            .first()
        )
        if conversation:
            return conversation

    conversation = models.Conversation(
        org_id=org_id,
        user_id=user_id,
        subscription_id=subscription_id,
        title=first_message[:120],
    )
    db.add(conversation)
    db.flush()
    return conversation
