"""Business profile endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DB, CurrentUser
from app.models import BusinessProfile, ProfileVersion
from app.schemas.common import OkOut
from app.schemas.profiles import (
    ProfileCreateIn,
    ProfileDuplicateIn,
    ProfileOut,
    ProfileUpdateIn,
    ProfileVersionOut,
)
from app.services import profiles as profile_service

router = APIRouter(prefix="/profiles", tags=["profiles"])


async def _out(db: AsyncSession, p: BusinessProfile, v: ProfileVersion) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "category_code": p.category_code,
        "category_name": await profile_service.category_name(db, p.category_code),
        "current_version": p.current_version,
        "is_default": p.is_default,
        "archived": p.archived_at is not None,
        "data": v.data,
        "summary": await profile_service.summary_for(db, p, v.data),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


@router.get("", response_model=list[ProfileOut])
async def list_profiles(db: DB, user: CurrentUser) -> list[ProfileOut]:
    return [ProfileOut(**await _out(db, p, v)) for p, v in await profile_service.list_profiles(db, user)]


@router.post("", response_model=ProfileOut, status_code=201)
async def create_profile(body: ProfileCreateIn, db: DB, user: CurrentUser) -> ProfileOut:
    p, v = await profile_service.create(
        db, user, name=body.name, category_code=body.category_code, data=body.data, is_default=body.is_default
    )
    return ProfileOut(**await _out(db, p, v))


@router.get("/{profile_id}", response_model=ProfileOut)
async def get_profile(profile_id: uuid.UUID, db: DB, user: CurrentUser) -> ProfileOut:
    p = await profile_service.get_owned(db, user, profile_id, include_archived=True)
    v = await profile_service.current_version(db, p)
    return ProfileOut(**await _out(db, p, v))


@router.put("/{profile_id}", response_model=ProfileOut)
async def update_profile(
    profile_id: uuid.UUID, body: ProfileUpdateIn, db: DB, user: CurrentUser
) -> ProfileOut:
    p, v = await profile_service.update(
        db, user, profile_id, name=body.name, data=body.data, is_default=body.is_default
    )
    return ProfileOut(**await _out(db, p, v))


@router.get("/{profile_id}/versions", response_model=list[ProfileVersionOut])
async def profile_versions(profile_id: uuid.UUID, db: DB, user: CurrentUser) -> list[ProfileVersionOut]:
    return [ProfileVersionOut(**v) for v in await profile_service.versions_with_tests(db, user, profile_id)]


@router.post("/{profile_id}/duplicate", response_model=ProfileOut, status_code=201)
async def duplicate_profile(
    profile_id: uuid.UUID, body: ProfileDuplicateIn | None, db: DB, user: CurrentUser
) -> ProfileOut:
    p, v = await profile_service.duplicate(db, user, profile_id, body.name if body else None)
    return ProfileOut(**await _out(db, p, v))


@router.delete("/{profile_id}", response_model=OkOut)
async def archive_profile(profile_id: uuid.UUID, db: DB, user: CurrentUser) -> OkOut:
    await profile_service.archive(db, user, profile_id)
    return OkOut(message="Profile archived; tests keep their snapshots")
