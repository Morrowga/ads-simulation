"""Admin exchange rates."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, AdminUser, Client
from app.schemas.admin import FxRatesIn
from app.schemas.config import FxRateOut
from app.services import audit, fx

router = APIRouter(prefix="/fx-rates", tags=["admin"])


def _out(r) -> FxRateOut:  # noqa: ANN001
    return FxRateOut(
        currency=r.currency,
        rate_per_usd=float(r.rate_per_usd),
        effective_date=r.effective_date,
        note=r.note,
        updated_at=r.updated_at,
    )


@router.get("", response_model=list[FxRateOut])
async def get_rates(db: DB, admin: AdminUser) -> list[FxRateOut]:
    return [_out(r) for r in await fx.all_rates(db)]


@router.put("", response_model=list[FxRateOut])
async def put_rates(body: FxRatesIn, db: DB, admin: AdminUser, client: Client) -> list[FxRateOut]:
    rows = await fx.upsert_rates(db, [r.model_dump() for r in body.rates], admin.id)
    await audit.log(
        db,
        actor_id=admin.id,
        action="admin.fx.update",
        entity="fx_rates",
        entity_id="all",
        data={"rates": [{"currency": r.currency, "rate_per_usd": float(r.rate_per_usd)} for r in rows]},
        ip=client.ip,
    )
    return [_out(r) for r in await fx.all_rates(db)]
