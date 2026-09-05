from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from . import models, schemas
from . import service_control
from .ai_engine import get_ai_engine
from .data_pipeline import aggregate_usage, generate_report
from .organizations.routes import router as organizations_router
from .organizations.routes import create_organization
from .plans.routes import router as plans_router
from .ingestion.routes import router as documents_router
from .rag.routes import router as rag_router
from .analytics.routes import router as analytics_router
from .audit.routes import router as audit_router
router = APIRouter(prefix="", tags=["api"])

router.include_router(plans_router)
router.include_router(organizations_router)
router.include_router(documents_router)
router.include_router(rag_router)
router.include_router(analytics_router)
router.include_router(audit_router)


@router.get("/ping")
async def ping() -> dict:
    return {"message": "pong"}


@router.post(
    "/auth/register",
    response_model=schemas.UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> models.User:
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = models.User(
        email=str(payload.email),
        hashed_password=service_control.hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if payload.org_name:
        create_organization(
            schemas.OrganizationCreate(name=payload.org_name),
            db=db,
            user=user,
        )

    return user


@router.post("/auth/login", response_model=schemas.Token)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)) -> schemas.Token:
    user = service_control.authenticate_user(db, str(payload.email), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = service_control.create_access_token(subject=user.email)
    return schemas.Token(access_token=token)


@router.post("/users", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> models.User:
    return register(payload, db)


@router.get("/users", response_model=list[schemas.UserRead])
def list_users(
    db: Session = Depends(get_db),
    _user: models.User = Depends(service_control.get_current_user),
) -> list[models.User]:
    return db.query(models.User).order_by(models.User.id.desc()).all()


@router.post(
    "/subscriptions",
    response_model=schemas.SubscriptionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subscription(
    payload: schemas.SubscriptionCreate,
    db: Session = Depends(get_db),
    _user: models.User = Depends(service_control.get_current_user),
) -> models.Subscription:
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan_name = payload.plan_name
    if payload.plan_id:
        plan = db.query(models.Plan).filter(models.Plan.id == payload.plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        plan_name = plan.name

    sub = models.Subscription(
        user_id=payload.user_id,
        org_id=payload.org_id,
        plan_id=payload.plan_id,
        plan_name=plan_name or "free",
        status=payload.status,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.post(
    "/usage-events",
    response_model=schemas.UsageEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_usage_event(
    payload: schemas.UsageEventCreate,
    db: Session = Depends(get_db),
    _user: models.User = Depends(service_control.get_current_user),
) -> models.UsageEvent:
    sub = (
        db.query(models.Subscription)
        .filter(models.Subscription.id == payload.subscription_id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    evt = models.UsageEvent(
        subscription_id=payload.subscription_id,
        org_id=payload.org_id or sub.org_id,
        event_type=payload.event_type,
        resource_type=payload.resource_type,
        payload=payload.payload,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


@router.post("/ai/chat/completions", response_model=schemas.ChatCompletionResponse)
def chat_completion(
    payload: schemas.ChatCompletionRequest,
    subscription_id: int,
    db: Session = Depends(get_db),
    ai_engine=Depends(get_ai_engine),
    user: models.User = Depends(service_control.get_current_user),
) -> schemas.ChatCompletionResponse:
    sub = (
        db.query(models.Subscription)
        .filter(
            models.Subscription.id == subscription_id,
            models.Subscription.user_id == user.id,
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=403, detail="Subscription not found or not owned by user")

    messages = [msg.model_dump() for msg in payload.messages]
    result = ai_engine.chat_completion(
        subscription_id=subscription_id,
        messages=messages,
        max_tokens=payload.max_tokens or 100,
        model=payload.model,
    )
    return schemas.ChatCompletionResponse(**result)


@router.get("/usage/stats/{subscription_id}")
def get_usage_stats(
    subscription_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(service_control.get_current_user),
):
    sub = db.query(models.Subscription).filter(
        models.Subscription.id == subscription_id,
        models.Subscription.user_id == user.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=403, detail="Subscription not found or not owned by user")

    return aggregate_usage(subscription_id, db)


@router.get("/usage/report/{subscription_id}")
def get_usage_report(
    subscription_id: int,
    format: str = "json",
    db: Session = Depends(get_db),
    user: models.User = Depends(service_control.get_current_user),
):
    sub = db.query(models.Subscription).filter(
        models.Subscription.id == subscription_id,
        models.Subscription.user_id == user.id,
    ).first()
    if not sub:
        raise HTTPException(status_code=403, detail="Subscription not found or not owned by user")

    report = generate_report(subscription_id, db, format)
    if format == "csv":
        from fastapi.responses import Response
        return Response(content=report, media_type="text/csv")
    return {"report": report}
