from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..analytics.metrics import get_document_stats, get_rag_stats, get_usage_stats, list_jobs
from ..data_pipeline import generate_report
from ..database import get_db
from ..organizations.rbac import get_org_member, require_org_role
from ..plans.quota import get_active_subscription

router = APIRouter(prefix="/orgs/{org_id}/analytics", tags=["analytics"])


@router.get("/usage", response_model=schemas.UsageStats)
def usage_analytics(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> schemas.UsageStats:
    subscription = get_active_subscription(db, org_id)
    if not subscription:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No active subscription")
    return get_usage_stats(db, subscription.id)


@router.get("/documents", response_model=schemas.DocumentStats)
def document_analytics(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> schemas.DocumentStats:
    return get_document_stats(db, org_id)


@router.get("/rag", response_model=schemas.RagStats)
def rag_analytics(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> schemas.RagStats:
    return get_rag_stats(db, org_id)


@router.get("/report")
def export_report(
    org_id: int,
    format: str = "json",
    _member: models.OrganizationMember = Depends(require_org_role("admin")),
    db: Session = Depends(get_db),
):
    subscription = get_active_subscription(db, org_id)
    if not subscription:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No active subscription")

    report = generate_report(subscription.id, db, format)
    if format == "csv":
        return Response(content=report, media_type="text/csv")
    return {"report": report}


@router.get("/jobs", response_model=list[schemas.JobRead])
def job_analytics(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> list[models.Job]:
    return list_jobs(db, org_id)
