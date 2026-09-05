from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..config import get_settings


class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def read(self, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str | None = None) -> None:
        settings = get_settings()
        self.base_path = Path(base_path or settings.storage_local_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        path = self.base_path / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, key: str, data: bytes) -> str:
        path = self._full_path(key)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return self._full_path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._full_path(key)
        if path.exists():
            path.unlink()


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        import boto3

        settings = get_settings()
        if not settings.aws_s3_bucket:
            raise RuntimeError("AWS_S3_BUCKET is required when STORAGE_BACKEND=s3")
        self.bucket = settings.aws_s3_bucket
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def save(self, key: str, data: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def read(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage()
