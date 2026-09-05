from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..audit.logger import log_audit
from ..database import get_db
from ..organizations.rbac import require_org_role
from ..rag.chat import clinical_chat
from ..service_control import get_current_user

router = APIRouter(prefix="/orgs/{org_id}", tags=["clinical-ai"])


@router.post("/chat", response_model=schemas.ClinicalChatResponse)
def rag_chat(
    org_id: int,
    payload: schemas.ClinicalChatRequest,
    request: Request,
    _member: models.OrganizationMember = Depends(require_org_role("clinician")),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ClinicalChatResponse:
    response = clinical_chat(db, org_id=org_id, user_id=user.id, payload=payload)
    log_audit(
        db,
        org_id=org_id,
        user_id=user.id,
        action="rag.query",
        resource_type="conversation",
        resource_id=response.conversation_id,
        details={"model": response.model, "citations": len(response.citations)},
        request=request,
    )
    return response


@router.get("/conversations", response_model=list[schemas.ConversationRead])
def list_conversations(
    org_id: int,
    _member: models.OrganizationMember = Depends(require_org_role("viewer")),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.Conversation]:
    return (
        db.query(models.Conversation)
        .filter(models.Conversation.org_id == org_id, models.Conversation.user_id == user.id)
        .order_by(models.Conversation.created_at.desc())
        .all()
    )


@router.get("/conversations/{conversation_id}", response_model=list[schemas.ConversationMessageRead])
def get_conversation_messages(
    org_id: int,
    conversation_id: int,
    _member: models.OrganizationMember = Depends(require_org_role("viewer")),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.ConversationMessage]:
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.org_id == org_id,
            models.Conversation.user_id == user.id,
        )
        .first()
    )
    if not conversation:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Conversation not found")

    return (
        db.query(models.ConversationMessage)
        .filter(models.ConversationMessage.conversation_id == conversation_id)
        .order_by(models.ConversationMessage.created_at.asc())
        .all()
    )
