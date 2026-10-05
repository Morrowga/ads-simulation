"""Object storage: S3-compatible (MinIO locally) via boto3, plus an in-memory backend for tests.
All uploads and generated files (frames, PDFs) live here, never in the project folder."""

from __future__ import annotations

import asyncio
import io
import logging
from functools import partial
from typing import Any, Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import get_settings

log = logging.getLogger("advar.storage")


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def presigned_url(
        self, key: str, ttl_sec: int | None = None, filename: str | None = None
    ) -> str: ...
    async def exists(self, key: str) -> bool: ...
    async def health(self) -> bool: ...


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (bytes(data), content_type)

    async def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise FileNotFoundError(key)
        return self.objects[key][0]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def presigned_url(self, key: str, ttl_sec: int | None = None, filename: str | None = None) -> str:
        s = get_settings()
        return f"{s.S3_PUBLIC_ENDPOINT.rstrip('/')}/{s.S3_BUCKET}/{key}?X-Amz-Expires={ttl_sec or s.PRESIGNED_URL_TTL_SEC}&memory=1"

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def health(self) -> bool:
        return True


class S3Storage:
    def __init__(self) -> None:
        s = get_settings()
        self.bucket = s.S3_BUCKET
        common: dict[str, Any] = dict(
            aws_access_key_id=s.S3_ACCESS_KEY,
            aws_secret_access_key=s.S3_SECRET_KEY,
            region_name=s.S3_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._client = boto3.client("s3", endpoint_url=s.S3_ENDPOINT, **common)
        # a second client whose endpoint is the browser-facing one, used only to sign URLs
        self._public_client = boto3.client("s3", endpoint_url=s.S3_PUBLIC_ENDPOINT or s.S3_ENDPOINT, **common)

    async def _run(self, fn, *args, **kwargs):  # noqa: ANN001
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await self._run(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
            ContentLength=len(data),
        )

    async def get(self, key: str) -> bytes:
        obj = await self._run(self._client.get_object, Bucket=self.bucket, Key=key)
        return await self._run(obj["Body"].read)

    async def delete(self, key: str) -> None:
        try:
            await self._run(self._client.delete_object, Bucket=self.bucket, Key=key)
        except ClientError as exc:
            log.warning("delete failed key=%s error=%s", key, exc)

    async def presigned_url(self, key: str, ttl_sec: int | None = None, filename: str | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return await self._run(
            self._public_client.generate_presigned_url,
            "get_object",
            Params=params,
            ExpiresIn=int(ttl_sec or get_settings().PRESIGNED_URL_TTL_SEC),
        )

    async def exists(self, key: str) -> bool:
        try:
            await self._run(self._client.head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def health(self) -> bool:
        try:
            await self._run(self._client.head_bucket, Bucket=self.bucket)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def ensure_bucket(self) -> None:
        try:
            await self._run(self._client.head_bucket, Bucket=self.bucket)
        except ClientError:
            try:
                await self._run(self._client.create_bucket, Bucket=self.bucket)
            except ClientError as exc:
                log.warning("could not create bucket %s: %s", self.bucket, exc)


class LocalStorage:
    """Filesystem backend for running the API and worker outside Docker without MinIO (dev only)."""

    def __init__(self, root: str) -> None:
        import pathlib

        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str):  # noqa: ANN202
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise FileNotFoundError(key)
        return p

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    async def presigned_url(self, key: str, ttl_sec: int | None = None, filename: str | None = None) -> str:
        # Dev-only: the API itself serves the file (see routers/local_files.py) since there is
        # no separate object-storage server running. Not a real signed URL, just a direct link.
        s = get_settings()
        url = f"{s.API_BASE_URL.rstrip('/')}/local-files/{key}"
        if filename:
            from urllib.parse import quote

            url += f"?filename={quote(filename)}"
        return url

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def health(self) -> bool:
        return self.root.exists()


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        if s.STORAGE_BACKEND == "memory":
            _storage = MemoryStorage()
        elif s.STORAGE_BACKEND == "local":
            _storage = LocalStorage(s.STORAGE_LOCAL_DIR)
        else:
            _storage = S3Storage()
    return _storage


def asset_key(test_id: str, asset_id: str, ext: str) -> str:
    return f"tests/{test_id}/assets/{asset_id}.{ext.lstrip('.')}"


def frame_key(test_id: str, asset_id: str, index: int) -> str:
    return f"tests/{test_id}/frames/{asset_id}_{index:03d}.jpg"


def audio_key(test_id: str, asset_id: str) -> str:
    return f"tests/{test_id}/audio/{asset_id}.mp3"


def report_pdf_key(test_id: str) -> str:
    return f"tests/{test_id}/report.pdf"
