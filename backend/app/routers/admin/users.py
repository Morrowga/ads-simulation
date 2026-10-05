"""Admin users: search, block/unblock, reset trial, role."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.deps import DB, AdminUser, Client, Page
from app.schemas.admin import AdminUserOut, AdminUserPatchIn
from app.schemas.common import Page as PageOut
from app.services import admin_service

router = APIRouter(prefix="/users", tags=["admin"])


@router.get("", response_model=PageOut[AdminUserOut])
async def list_users(
    db: DB, admin: AdminUser, page: Page, q: str | None = Query(default=None)
) -> PageOut[AdminUserOut]:
    items, next_cursor = await admin_service.list_users(db, page.cursor, page.limit, q)
    return PageOut[AdminUserOut](items=[AdminUserOut(**i) for i in items], next_cursor=next_cursor)


@router.patch("/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: uuid.UUID, body: AdminUserPatchIn, db: DB, admin: AdminUser, client: Client
) -> AdminUserOut:
    return AdminUserOut(
        **await admin_service.patch_user(
            db,
            admin,
            user_id,
            is_blocked=body.is_blocked,
            reset_trial=body.reset_trial,
            role=body.role,
            ip=client.ip,
        )
    )
