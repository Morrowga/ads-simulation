"""Idempotent seed: admin user, tiers, prices, countries (published v1), fx rates, scenarios,
weight set v1, platforms (published v1), category templates (published v1), default settings.

    python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import dispose_engine, session_scope
from app.models import (
    CategoryTemplate,
    Country,
    CountryVersion,
    FxRate,
    Platform,
    PlatformSettings,
    Price,
    Scenario,
    Tier,
    User,
    WeightSet,
)
from app.security import hash_password
from app.services import settings_service
from app.services.auth_service import normalize_email
from engine.data_loader import (
    DEFAULT_TIERS,
    load_categories,
    load_countries,
    load_platforms,
    load_scenarios,
    load_weights,
)

log = logging.getLogger("advar.seed")

PRICES_USD = {"quick": 500, "standard": 1200, "full": 2500, "extra_platform": 600}
# Placeholder exchange rates, clearly marked; the admin updates them in the dashboard.
FX_PLACEHOLDERS = {
    "THB": ("33.500000", "PLACEHOLDER rate, update in admin"),
    "MMK": ("2100.000000", "PLACEHOLDER rate, update in admin"),
}


async def seed_admin(db: AsyncSession) -> None:
    s = get_settings()
    existing = (await db.execute(select(User).where(User.email == s.SEED_ADMIN_EMAIL))).scalar_one_or_none()
    if existing is None:
        db.add(
            User(
                email=s.SEED_ADMIN_EMAIL,
                email_normalized=normalize_email(s.SEED_ADMIN_EMAIL),
                password_hash=hash_password(s.SEED_ADMIN_PASSWORD),
                name="Admin",
                role="admin",
                email_verified_at=datetime.now(UTC),
                locale="en",
                country="TH",
            )
        )
        log.info("admin user created: %s", s.SEED_ADMIN_EMAIL)
    elif existing.role != "admin":
        existing.role = "admin"


async def seed_tiers_and_prices(db: AsyncSession) -> None:
    for t in DEFAULT_TIERS:
        row = await db.get(Tier, t["code"])
        if row is None:
            db.add(Tier(**t, active=True))
    for code, amount in PRICES_USD.items():
        row = (
            await db.execute(select(Price).where(Price.tier_code == code, Price.currency == "USD"))
        ).scalar_one_or_none()
        if row is None:
            db.add(
                Price(
                    tier_code=code,
                    currency="USD",
                    amount_minor=amount,
                    extra_platform_minor=PRICES_USD["extra_platform"] if code != "extra_platform" else 0,
                    method="any",
                    active=True,
                )
            )


async def seed_countries(db: AsyncSession) -> None:
    for code, d in load_countries().items():
        country = await db.get(Country, code)
        if country is None:
            country = Country(
                code=code,
                name=d["name"],
                currency=d["currency"],
                payment_methods=list(d.get("payment_methods", ["card"])),
                active=True,
            )
            db.add(country)
            await db.flush()
        version = int(d.get("version", 1))
        existing = (
            await db.execute(
                select(CountryVersion).where(
                    CountryVersion.country_code == code, CountryVersion.version == version
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                CountryVersion(
                    country_code=code,
                    version=version,
                    data=d.get("data", {}),
                    sources=d.get("sources", {}),
                    change_note=d.get("change_note", "seed"),
                    status="published",
                    published_at=datetime.now(UTC),
                )
            )
            country.current_version = version
        elif country.current_version is None:
            country.current_version = version


async def seed_fx(db: AsyncSession) -> None:
    for cur, (rate, note) in FX_PLACEHOLDERS.items():
        row = (await db.execute(select(FxRate).where(FxRate.currency == cur))).scalar_one_or_none()
        if row is None:
            db.add(FxRate(currency=cur, rate_per_usd=Decimal(rate), effective_date=date.today(), note=note))


async def seed_scenarios(db: AsyncSession) -> None:
    for s in load_scenarios():
        existing = (
            await db.execute(
                select(Scenario).where(
                    Scenario.code == s["code"], Scenario.version == int(s.get("version", 1))
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            mods = dict(s.get("modifiers", {}))
            if s.get("description"):
                mods["description"] = s["description"]
            db.add(
                Scenario(
                    code=s["code"],
                    name=s["name"],
                    version=int(s.get("version", 1)),
                    modifiers=mods,
                    country_codes=list(s.get("country_codes", [])),
                    category_codes=list(s.get("category_codes", [])),
                    date_rules=dict(s.get("date_rules", {})),
                    weight=float(s.get("weight", 1.0)),
                    active=bool(s.get("active", True)),
                    status="published",
                    change_note="seed",
                    published_at=datetime.now(UTC),
                )
            )


async def seed_weights(db: AsyncSession) -> None:
    w = load_weights()
    existing = (
        await db.execute(select(WeightSet).where(WeightSet.version == w["version"]))
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            WeightSet(
                version=w["version"],
                behavior=w["behavior"],
                score_by_goal=w["score_by_goal"],
                status="published",
                change_note=w.get("change_note", "seed"),
                published_at=datetime.now(UTC),
            )
        )


async def seed_platforms(db: AsyncSession) -> None:
    order = {"facebook": 1, "instagram": 2, "tiktok": 3}
    for code, p in load_platforms().items():
        platform = await db.get(Platform, code)
        if platform is None:
            platform = Platform(
                code=code, name=p["name"], status=p["status"], active=True, sort_order=order.get(code, 9)
            )
            db.add(platform)
            await db.flush()
        existing = (
            await db.execute(
                select(PlatformSettings).where(
                    PlatformSettings.platform_code == code, PlatformSettings.version == p["version"]
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                PlatformSettings(
                    platform_code=code,
                    version=p["version"],
                    global_config=p["global"],
                    markets=p["markets"],
                    sources=p["sources"],
                    status="published",
                    change_note=p.get("change_note", "seed"),
                    published_at=datetime.now(UTC),
                )
            )
            platform.current_version = p["version"]
        elif platform.current_version is None:
            platform.current_version = p["version"]


async def seed_categories(db: AsyncSession) -> None:
    fields = (
        "questions",
        "trait_dimensions",
        "activation_rules",
        "default_mixes",
        "buying_behavior",
        "blockers",
        "trust_signals",
        "comment_topics",
        "typical_goals",
        "analyzer_hints",
        "benchmark_adjustments",
        "calendar",
        "restrictions",
        "country_overrides",
    )
    for code, c in load_categories().items():
        version = int(c.get("version", 1))
        existing = (
            await db.execute(
                select(CategoryTemplate).where(
                    CategoryTemplate.code == code, CategoryTemplate.version == version
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            row = CategoryTemplate(
                code=code,
                name=c["name"],
                parent_code=c.get("parent_code"),
                tags=list(c.get("tags", [])),
                version=version,
                status="published",
                change_note=c.get("change_note", "seed"),
                published_at=datetime.now(UTC),
                active=True,
            )
            for f in fields:
                setattr(
                    row,
                    f,
                    c.get(f)
                    or (
                        {}
                        if f
                        in (
                            "default_mixes",
                            "buying_behavior",
                            "analyzer_hints",
                            "benchmark_adjustments",
                            "calendar",
                            "restrictions",
                            "country_overrides",
                        )
                        else []
                    ),
                )
            db.add(row)


async def run() -> None:
    async with session_scope() as db:
        await seed_admin(db)
        await seed_tiers_and_prices(db)
        await seed_countries(db)
        await seed_fx(db)
        await seed_scenarios(db)
        await seed_weights(db)
        await seed_platforms(db)
        await seed_categories(db)
        await settings_service.ensure_defaults(db)
    log.info("seed complete")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    async def _main() -> None:
        try:
            await run()
        finally:
            await dispose_engine()

    asyncio.run(_main())


if __name__ == "__main__":
    main()
