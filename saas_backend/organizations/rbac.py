from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..service_control import get_current_user

ROLE_HIERARCHY = {"viewer": 1, "clinician": 2, "admin": 3}


def get_org_member(
    org_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.OrganizationMember:
    member = (
        db.query(models.OrganizationMember)
        .filter(
            models.OrganizationMember.org_id == org_id,
            models.OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return member


def require_org_role(min_role: str):
    def dependency(
        member: models.OrganizationMember = Depends(get_org_member),
    ) -> models.OrganizationMember:
        if ROLE_HIERARCHY.get(member.role, 0) < ROLE_HIERARCHY.get(min_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role} role or higher",
            )
        return member

    return dependency
