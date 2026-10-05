"""Media upload endpoints (multipart)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile

from app.config import get_settings
from app.deps import DB, CurrentUser
from app.errors import ApiError, ErrorCode
from app.schemas.common import OkOut
from app.schemas.tests import AssetOut
from app.services import rate_limit, serializers, tests_service

router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("/{test_id}/assets", response_model=AssetOut, status_code=201)
async def upload_asset(
    test_id: uuid.UUID, db: DB, user: CurrentUser, file: UploadFile = File(...)
) -> AssetOut:
    await rate_limit.enforce(rate_limit.UPLOAD, str(user.id))
    s = get_settings()
    limit = s.MAX_VIDEO_BYTES + 1024
    chunks = []
    size = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise ApiError(
                ErrorCode.asset_too_large, f"File is larger than {s.MAX_VIDEO_BYTES // (1024 * 1024)} MB"
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ApiError(ErrorCode.asset_invalid, "Empty file")
    asset = await tests_service.add_asset(db, user, test_id, data, file.filename)
    return AssetOut(**await serializers.asset_out(asset))


@router.delete("/{test_id}/assets/{asset_id}", response_model=OkOut)
async def delete_asset(test_id: uuid.UUID, asset_id: uuid.UUID, db: DB, user: CurrentUser) -> OkOut:
    await tests_service.delete_asset(db, user, test_id, asset_id)
    return OkOut(message="Asset removed")
