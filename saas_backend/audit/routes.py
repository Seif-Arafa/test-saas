from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import models, schemas
from .database import get_db
from .organizations.rbac import require_org_role

router = APIRouter(prefix="/orgs/{org_id}/audit-logs", tags=["audit"])


@router.get("", response_model=list[schemas.AuditLogRead])
def list_audit_logs(
    org_id: int,
    _admin: models.OrganizationMember = Depends(require_org_role("admin")),
    db: Session = Depends(get_db),
) -> list[models.AuditLog]:
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.org_id == org_id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
