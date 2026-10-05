"""Admin prices (USD)."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, AdminUser, Client
from app.schemas.admin import PricesIn, PricesOut
from app.services import admin_service

router = APIRouter(prefix="/prices", tags=["admin"])


@router.get("", response_model=PricesOut)
async def get_prices(db: DB, admin: AdminUser) -> PricesOut:
    return PricesOut(**await admin_service.get_prices(db))


@router.put("", response_model=PricesOut)
async def put_prices(body: PricesIn, db: DB, admin: AdminUser, client: Client) -> PricesOut:
    return PricesOut(
        **await admin_service.put_prices(
            db, admin, [i.model_dump() for i in body.items], body.change_note, client.ip
        )
    )
