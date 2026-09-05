from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..plans.catalog import slugify
from ..service_control import get_current_user
from .rbac import get_org_member, require_org_role

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=schemas.OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: schemas.OrganizationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Organization:
    slug = payload.slug or slugify(payload.name)
    existing = db.query(models.Organization).filter(models.Organization.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Organization slug already exists")

    org = models.Organization(
        name=payload.name,
        slug=slug,
        settings={"disclaimer": "For clinical reference only. Not a substitute for professional judgment."},
    )
    db.add(org)
    db.flush()

    db.add(models.OrganizationMember(org_id=org.id, user_id=user.id, role="admin"))

    free_plan = db.query(models.Plan).filter(models.Plan.name == "free").first()
    db.add(
        models.Subscription(
            user_id=user.id,
            org_id=org.id,
            plan_id=free_plan.id if free_plan else None,
            plan_name="free",
            status="active",
        )
    )
    db.commit()
    db.refresh(org)
    return org


@router.get("", response_model=list[schemas.OrganizationRead])
def list_my_organizations(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.Organization]:
    org_ids = [
        m.org_id
        for m in db.query(models.OrganizationMember)
        .filter(models.OrganizationMember.user_id == user.id)
        .all()
    ]
    if not org_ids:
        return []
    return db.query(models.Organization).filter(models.Organization.id.in_(org_ids)).all()


@router.get("/{org_id}", response_model=schemas.OrganizationRead)
def get_organization(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> models.Organization:
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post(
    "/{org_id}/members",
    response_model=schemas.OrganizationMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    org_id: int,
    payload: schemas.OrganizationMemberCreate,
    _admin: models.OrganizationMember = Depends(require_org_role("admin")),
    db: Session = Depends(get_db),
) -> models.OrganizationMember:
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(models.OrganizationMember)
        .filter(
            models.OrganizationMember.org_id == org_id,
            models.OrganizationMember.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")

    member = models.OrganizationMember(org_id=org_id, user_id=payload.user_id, role=payload.role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{org_id}/members", response_model=list[schemas.OrganizationMemberRead])
def list_members(
    org_id: int,
    _member: models.OrganizationMember = Depends(get_org_member),
    db: Session = Depends(get_db),
) -> list[models.OrganizationMember]:
    return db.query(models.OrganizationMember).filter(models.OrganizationMember.org_id == org_id).all()
