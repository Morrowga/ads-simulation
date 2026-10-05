"""Exchange rates for local price display and Myanmar manual orders (fixed on the order)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FxRate

CURRENCY_SYMBOL = {
    "USD": "$",
    "THB": "฿",
    "MMK": "K",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "SGD": "S$",
    "MYR": "RM",
    "VND": "₫",
    "IDR": "Rp",
    "PHP": "₱",
}
ZERO_DECIMAL = {"MMK", "JPY", "VND", "IDR", "KRW"}
# rounding of local display amounts to friendly units
ROUND_TO = {"MMK": 100, "VND": 1000, "IDR": 1000, "JPY": 10, "KRW": 100}


def minor_units(currency: str) -> int:
    return 1 if currency.upper() in ZERO_DECIMAL else 100


def format_money(amount_minor: int, currency: str, approximate: bool = False) -> str:
    cur = currency.upper()
    units = minor_units(cur)
    sym = CURRENCY_SYMBOL.get(cur, cur + " ")
    if units == 1:
        body = f"{sym}{amount_minor:,.0f}"
    else:
        body = f"{sym}{amount_minor / units:,.2f}"
    if cur not in CURRENCY_SYMBOL:
        body = f"{cur} {body[len(cur) + 1 :]}"
    return ("= " if approximate else "") + body


async def get_rate(db: AsyncSession, currency: str) -> FxRate | None:
    cur = currency.upper()
    if cur == "USD":
        return None
    res = await db.execute(select(FxRate).where(FxRate.currency == cur))
    return res.scalar_one_or_none()


async def all_rates(db: AsyncSession) -> list[FxRate]:
    res = await db.execute(select(FxRate).order_by(FxRate.currency))
    return list(res.scalars().all())


def convert_usd_minor(
    amount_usd_minor: int, rate_per_usd: Decimal | float, currency: str, friendly: bool = True
) -> int:
    cur = currency.upper()
    usd = Decimal(amount_usd_minor) / Decimal(100)
    local = usd * Decimal(str(rate_per_usd))
    local_minor = local * Decimal(minor_units(cur))
    value = int(local_minor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if friendly and cur in ROUND_TO:
        step = ROUND_TO[cur]
        value = int(round(value / step) * step)
    return value


async def local_amount(
    db: AsyncSession, amount_usd_minor: int, currency: str, friendly: bool = True
) -> dict[str, Any] | None:
    """Approximate local amount for display; None when the currency is USD or has no rate."""
    cur = currency.upper()
    if cur == "USD":
        return None
    rate = await get_rate(db, cur)
    if rate is None:
        return None
    value = convert_usd_minor(amount_usd_minor, rate.rate_per_usd, cur, friendly=friendly)
    return {
        "currency": cur,
        "amount_minor": value,
        "fx_rate": float(rate.rate_per_usd),
        "approximate": True,
        "display": format_money(value, cur, approximate=True),
    }


async def upsert_rates(db: AsyncSession, rates: list[dict[str, Any]], updated_by) -> list[FxRate]:  # noqa: ANN001
    out = []
    for r in rates:
        cur = str(r["currency"]).upper()
        if cur == "USD":
            continue
        res = await db.execute(select(FxRate).where(FxRate.currency == cur))
        row = res.scalar_one_or_none()
        eff = r.get("effective_date") or datetime.now(UTC).date()
        if isinstance(eff, str):
            eff = date.fromisoformat(eff)
        if row is None:
            row = FxRate(
                currency=cur,
                rate_per_usd=Decimal(str(r["rate_per_usd"])),
                effective_date=eff,
                updated_by=updated_by,
                note=str(r.get("note", "")),
            )
            db.add(row)
        else:
            row.rate_per_usd = Decimal(str(r["rate_per_usd"]))
            row.effective_date = eff
            row.updated_by = updated_by
            row.note = str(r.get("note", row.note))
        out.append(row)
    await db.flush()
    return out
