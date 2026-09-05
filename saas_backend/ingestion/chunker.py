from __future__ import annotations

import re


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    words = text.split(" ")
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = max(end - overlap, start + 1)
    return chunks


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
