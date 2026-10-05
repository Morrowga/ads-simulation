"""Dev-only file server for STORAGE_BACKEND=local.

When there's no MinIO/S3 running, LocalStorage saves files to disk and hands out URLs that
point back at this router so the frontend can still fetch them. Not used in production
(STORAGE_BACKEND=s3 there), so this stays intentionally simple: read-only, no auth, 404s
whenever local storage isn't the active backend.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.services.storage import get_storage, LocalStorage

router = APIRouter(tags=["internal"])


@router.get("/local-files/{key:path}")
async def get_local_file(key: str) -> FileResponse:
    s = get_settings()
    if s.STORAGE_BACKEND != "local":
        raise HTTPException(status_code=404, detail="Not found")
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        path = storage._path(key)  # noqa: SLF001 (same module concern, dev-only helper)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found") from None
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)