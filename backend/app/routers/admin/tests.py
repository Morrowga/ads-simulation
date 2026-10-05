"""Admin tests: list, detail (stages, cost, errors), re-run."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.deps import DB, AdminUser, Client, Page
from app.schemas.admin import AdminTestListItem, AdminTestOut
from app.schemas.common import Page as PageOut
from app.services import admin_service

router = APIRouter(prefix="/tests", tags=["admin"])


@router.get("", response_model=PageOut[AdminTestListItem])
async def list_tests(
    db: DB,
    admin: AdminUser,
    page: Page,
    status: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
) -> PageOut[AdminTestListItem]:
    items, next_cursor = await admin_service.list_tests(db, page.cursor, page.limit, status, user_email)
    return PageOut[AdminTestListItem](items=[AdminTestListItem(**i) for i in items], next_cursor=next_cursor)


@router.get("/{test_id}", response_model=AdminTestOut)
async def get_test(test_id: uuid.UUID, db: DB, admin: AdminUser) -> AdminTestOut:
    return AdminTestOut(**await admin_service.test_detail(db, test_id))


@router.post("/{test_id}/rerun", response_model=AdminTestOut)
async def rerun_test(test_id: uuid.UUID, db: DB, admin: AdminUser, client: Client) -> AdminTestOut:
    await admin_service.rerun_test(db, admin, test_id, client.ip)
    return AdminTestOut(**await admin_service.test_detail(db, test_id))
