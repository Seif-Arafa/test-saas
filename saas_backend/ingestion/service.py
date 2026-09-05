from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from .. import models
from ..ingestion.chunker import chunk_text, estimate_tokens
from ..ingestion.parsers import parse_document
from ..ingestion.storage import get_storage
from ..rag.embedder import embed_texts


def ingest_document_record(db: Session, document_id: int) -> dict:
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document {document_id} not found")

    document.status = "processing"
    document.error_message = None
    db.commit()

    storage = get_storage()
    try:
        raw = storage.read(document.storage_key)
        text = parse_document(document.title, raw)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No extractable text found in document")

        db.query(models.DocumentChunk).filter(models.DocumentChunk.document_id == document.id).delete()

        embeddings = embed_texts(chunks)
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db.add(
                models.DocumentChunk(
                    document_id=document.id,
                    org_id=document.org_id,
                    chunk_index=index,
                    content=chunk,
                    token_count=estimate_tokens(chunk),
                    embedding=embedding,
                    metadata_json={"doc_type": document.doc_type, **document.metadata_json},
                )
            )

        document.status = "ready"
        document.updated_at = datetime.utcnow()
        db.commit()
        return {"document_id": document.id, "chunks": len(chunks), "status": "ready"}
    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)
        document.updated_at = datetime.utcnow()
        db.commit()
        raise


def build_storage_key(org_id: int, filename: str) -> str:
    safe_name = filename.replace("\\", "_").replace("/", "_")
    return f"orgs/{org_id}/{uuid.uuid4().hex}_{safe_name}"
