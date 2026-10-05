"""GET /countries and GET /tiers."""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import DB
from app.models import Country, CountryVersion
from app.schemas.config import CountryOut, TierOut
from app.services import pricing, serializers

router = APIRouter(tags=["config"])


@router.get("/countries", response_model=list[CountryOut])
async def list_countries(db: DB) -> list[CountryOut]:
    rows = (
        (await db.execute(select(Country).where(Country.active.is_(True)).order_by(Country.name)))
        .scalars()
        .all()
    )
    out = []
    for c in rows:
        ver = (
            (
                await db.execute(
                    select(CountryVersion)
                    .where(CountryVersion.country_code == c.code, CountryVersion.status == "published")
                    .order_by(CountryVersion.version.desc())
                )
            )
            .scalars()
            .first()
        )
        if ver is None:
            continue
        out.append(CountryOut(**await serializers.country_out(db, c, ver.data, ver.version)))
    return out


@router.get("/tiers", response_model=list[TierOut])
async def list_tiers(
    db: DB,
    country: str | None = Query(default=None, min_length=2, max_length=2),
    platforms: int = Query(default=1, ge=1, le=5),
) -> list[TierOut]:
    local_currency = None
    if country:
        c = await db.get(Country, country.upper())
        local_currency = c.currency if c else None
    rows = await pricing.tiers_with_prices(db, local_currency, platforms)
    return [TierOut(**{k: v for k, v in r.items() if k in TierOut.model_fields}) for r in rows]
