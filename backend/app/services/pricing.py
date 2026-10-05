"""Prices are read from the database only. Total = tier price + (platforms - 1) x extra platform price, in USD."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import Price, Tier
from app.services import fx


async def load_prices(db: AsyncSession, currency: str = "USD") -> dict[str, Price]:
    res = await db.execute(select(Price).where(Price.currency == currency.upper(), Price.active.is_(True)))
    return {p.tier_code: p for p in res.scalars().all()}


async def load_tiers(db: AsyncSession, include_inactive: bool = False) -> list[Tier]:
    stmt = select(Tier).order_by(Tier.sort_order)
    if not include_inactive:
        stmt = stmt.where(Tier.active.is_(True))
    res = await db.execute(stmt)
    return list(res.scalars().all())


def compute_total(prices: dict[str, Price], tier_code: str, platform_count: int) -> dict[str, int]:
    tier_price = prices.get(tier_code)
    if tier_price is None:
        raise ApiError(ErrorCode.validation_error, f"No price configured for tier '{tier_code}'")
    extra_row = prices.get("extra_platform")
    extra_unit = (
        int(extra_row.amount_minor) if extra_row is not None else int(tier_price.extra_platform_minor)
    )
    extra_count = max(0, int(platform_count) - 1)
    return {
        "tier_usd_minor": int(tier_price.amount_minor),
        "extra_platform_usd_minor": extra_unit,
        "extra_platforms": extra_count,
        "total_usd_minor": int(tier_price.amount_minor) + extra_count * extra_unit,
    }


async def price_for(
    db: AsyncSession, tier_code: str, platform_count: int, local_currency: str | None = None
) -> dict[str, Any]:
    prices = await load_prices(db)
    total = compute_total(prices, tier_code, platform_count)
    out: dict[str, Any] = {
        "tier_code": tier_code,
        **total,
        "display": fx.format_money(total["total_usd_minor"], "USD"),
        "local": None,
    }
    if local_currency and local_currency.upper() != "USD":
        out["local"] = await fx.local_amount(db, total["total_usd_minor"], local_currency)
    return out


async def tiers_with_prices(
    db: AsyncSession, local_currency: str | None, platform_count: int = 1
) -> list[dict[str, Any]]:
    prices = await load_prices(db)
    tiers = await load_tiers(db)
    out = []
    for t in tiers:
        if t.code not in prices:
            continue
        total = compute_total(prices, t.code, platform_count)
        local = await fx.local_amount(db, total["tier_usd_minor"], local_currency) if local_currency else None
        extra_local = (
            await fx.local_amount(db, total["extra_platform_usd_minor"], local_currency)
            if local_currency
            else None
        )
        out.append(
            {
                "code": t.code,
                "name": t.name,
                "runs_target": t.runs_target,
                "min_runs": t.min_runs,
                "scenarios": t.scenarios,
                "max_audiences": t.max_audiences,
                "agents": t.agents,
                "archetypes": t.archetypes,
                "price_usd_minor": total["tier_usd_minor"],
                "price_display": fx.format_money(total["tier_usd_minor"], "USD"),
                "extra_platform_usd_minor": total["extra_platform_usd_minor"],
                "extra_platform_display": fx.format_money(total["extra_platform_usd_minor"], "USD"),
                "local": local,
                "extra_platform_local": extra_local,
                "total_usd_minor": total["total_usd_minor"],
                "extra_platforms": total["extra_platforms"],
            }
        )
    return out
