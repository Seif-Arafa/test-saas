from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..audit.logger import log_audit
from ..database import get_db
from ..ingestion.service import build_storage_key, ingest_document_record
from ..ingestion.storage import get_storage
from ..jobs.tasks import enqueue_ingest_document
from ..organizations.rbac import require_org_role
from ..plans.quota import (
    enforce_document_quota,
    get_active_subscription,
    get_plan_for_subscription,
)
from ..service_control import get_current_user

router = APIRouter(prefix="/orgs/{org_id}/documents", tags=["documents"])

ALLOWED_DOC_TYPES = {"guideline", "protocol", "formulary", "lab_ref", "policy"}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc"}


@router.post("/upload", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    org_id: int,
    request: Request,
    file: UploadFile = File(...),
    doc_type: str = Form(default="guideline"),
    specialty: str | None = Form(default=None),
    _member: models.OrganizationMember = Depends(require_org_role("clinician")),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.Document:
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {sorted(ALLOWED_DOC_TYPES)}")

    filename = file.filename or "upload.txt"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    subscription = get_active_subscription(db, org_id)
    if not subscription:
        raise HTTPException(status_code=403, detail="No active subscription for this organization")

    plan = get_plan_for_subscription(db, subscription)
    if not plan:
        raise HTTPException(status_code=403, detail="Plan not found")

    enforce_document_quota(db, org_id, plan, len(data))

    storage_key = build_storage_key(org_id, filename)
    get_storage().save(storage_key, data)

    metadata = {"specialty": specialty} if specialty else {}
    document = models.Document(
        org_id=org_id,
        subscription_id=subscription.id,
        title=filename,
        doc_type=doc_type,
        source="upload",
        storage_key=storage_key,
        file_size_bytes=len(data),
        status="pending",
        metadata_json=metadata,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    job = models.Job(
        org_id=org_id,
        job_type="ingest_document",
        status="queued",
        payload={"document_id": document.id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task_id = enqueue_ingest_document(document.id, job.id)
    job.celery_task_id = task_id
    db.commit()

    log_audit(
        db,
        org_id=org_id,
        user_id=user.id,
        action="document.upload",
        resource_type="document",
        resource_id=document.id,
        details={"filename": filename, "doc_type": doc_type},
        request=request,
    )
    return document


@router.get("", response_model=list[schemas.DocumentRead])
def list_documents(
    org_id: int,
    _member: models.OrganizationMember = Depends(require_org_role("viewer")),
    db: Session = Depends(get_db),
) -> list[models.Document]:
    return (
        db.query(models.Document)
        .filter(models.Document.org_id == org_id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.get("/{document_id}", response_model=schemas.DocumentRead)
def get_document(
    org_id: int,
    document_id: int,
    _member: models.OrganizationMember = Depends(require_org_role("viewer")),
    db: Session = Depends(get_db),
) -> models.Document:
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == org_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    org_id: int,
    document_id: int,
    request: Request,
    _member: models.OrganizationMember = Depends(require_org_role("admin")),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> None:
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == org_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        get_storage().delete(document.storage_key)
    except Exception:
        pass

    db.delete(document)
    db.commit()

    log_audit(
        db,
        org_id=org_id,
        user_id=user.id,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        request=request,
    )


@router.post("/{document_id}/reindex", response_model=schemas.JobRead)
def reindex_document(
    org_id: int,
    document_id: int,
    _member: models.OrganizationMember = Depends(require_org_role("clinician")),
    db: Session = Depends(get_db),
) -> models.Job:
    document = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.org_id == org_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    job = models.Job(
        org_id=org_id,
        job_type="ingest_document",
        status="queued",
        payload={"document_id": document.id},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task_id = enqueue_ingest_document(document.id, job.id)
    job.celery_task_id = task_id
    db.commit()
    db.refresh(job)
    return job
