from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .embedder import embed_query

CLINICAL_DISCLAIMER = (
    "For clinical reference only. Not a substitute for professional medical judgment, "
    "diagnosis, or treatment."
)

SYSTEM_PROMPT = f"""You are a clinical reference assistant for healthcare professionals.
Answer ONLY using the provided context from clinical documents (guidelines, protocols, formularies, lab references).
Always cite which source sections support your answer.
If the context is insufficient, say you cannot answer from the available documents.
Do not diagnose patients or prescribe treatments.
End every response with: "{CLINICAL_DISCLAIMER}"
"""


def retrieve_chunks(
    db: Session,
    org_id: int,
    query: str,
    *,
    doc_types: list[str] | None = None,
    specialty: str | None = None,
    top_k: int = 8,
) -> list[tuple[models.DocumentChunk, models.Document, float]]:
    query_embedding = embed_query(query)

    stmt = (
        select(
            models.DocumentChunk,
            models.Document,
            models.DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
        .where(
            models.DocumentChunk.org_id == org_id,
            models.Document.status == "ready",
            models.DocumentChunk.embedding.isnot(None),
        )
        .order_by("distance")
        .limit(top_k * 3)
    )

    rows = db.execute(stmt).all()
    results: list[tuple[models.DocumentChunk, models.Document, float]] = []
    for chunk, document, distance in rows:
        if doc_types and document.doc_type not in doc_types:
            continue
        if specialty:
            doc_specialty = (document.metadata_json or {}).get("specialty")
            if doc_specialty and doc_specialty != specialty:
                continue
        results.append((chunk, document, float(distance)))
        if len(results) >= top_k:
            break
    return results


def build_context(chunks: list[tuple[models.DocumentChunk, models.Document, float]]) -> str:
    parts: list[str] = []
    for index, (chunk, document, _distance) in enumerate(chunks, start=1):
        page = (chunk.metadata_json or {}).get("page")
        page_suffix = f" (page {page})" if page else ""
        parts.append(
            f"[Source {index}] Document: {document.title}{page_suffix}\n{chunk.content}"
        )
    return "\n\n".join(parts)
