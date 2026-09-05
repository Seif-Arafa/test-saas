from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[schemas.PlanRead])
def list_plans(db: Session = Depends(get_db)) -> list[models.Plan]:
    return db.query(models.Plan).order_by(models.Plan.price_cents.asc()).all()
