"""GET /admin/metrics."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import DB, AdminUser
from app.schemas.admin import AdminMetricsOut
from app.services import admin_service

router = APIRouter(prefix="/metrics", tags=["admin"])


@router.get("", response_model=AdminMetricsOut)
async def get_metrics(
    db: DB, admin: AdminUser, days: int = Query(default=30, ge=1, le=365)
) -> AdminMetricsOut:
    return AdminMetricsOut(**await admin_service.metrics(db, days))
