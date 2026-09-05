from __future__ import annotations

from pathlib import Path


def parse_document(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return data.decode("utf-8", errors="ignore")
    if suffix == ".pdf":
        return _parse_pdf(data)
    if suffix in {".docx", ".doc"}:
        return _parse_docx(data)
    raise ValueError(f"Unsupported file type: {suffix}")


def _parse_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def _parse_docx(data: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
