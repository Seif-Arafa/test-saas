from __future__ import annotations

from ..config import get_settings


def get_openai_client():
    import openai

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required")
    return openai.OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
