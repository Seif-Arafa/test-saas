from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://clinical:clinical@localhost:5432/clinical_saas",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    openai_embedding_dimensions: int = int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_task_always_eager: bool = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local")
    storage_local_path: str = os.getenv("STORAGE_LOCAL_PATH", "./storage")
    aws_s3_bucket: str | None = os.getenv("AWS_S3_BUCKET")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        if origin.strip()
    ]
