"""Versioned admin settings (countries, categories, platforms, scenarios, weights):
draft -> publish -> rollback, plus loading the published layers for the engine resolver."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import (
    CategoryTemplate,
    Country,
    CountryVersion,
    Platform,
    PlatformSettings,
    Scenario,
    Tier,
    WeightSet,
)
from app.security import now_utc
from app.services import audit, settings_service
from engine.simulation.config.resolver import resolve
from engine.simulation.types import FrozenConfig

KINDS = ("countries", "categories", "platforms", "scenarios", "weights")

CATEGORY_FIELDS = (
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
    "tags",
    "parent_code",
)


# --------------------------------------------------------------------------- published loaders


async def published_country(db: AsyncSession, code: str) -> dict[str, Any]:
    country = await db.get(Country, code.upper())
    if country is None or not country.active:
        raise ApiError(ErrorCode.country_not_active, f"Country {code} is not available")
    res = await db.execute(
        select(CountryVersion)
        .where(CountryVersion.country_code == country.code, CountryVersion.status == "published")
        .order_by(CountryVersion.version.desc())
    )
    ver = res.scalars().first()
    if ver is None:
        raise ApiError(ErrorCode.settings_not_published, f"Country {code} has no published settings")
    return {
        "code": country.code,
        "name": country.name,
        "currency": country.currency,
        "payment_methods": list(country.payment_methods),
        "version": ver.version,
        "data": ver.data,
        "sources": ver.sources,
    }


async def published_platform(db: AsyncSession, code: str) -> dict[str, Any]:
    platform = await db.get(Platform, code)
    if platform is None or not platform.active:
        raise ApiError(ErrorCode.platform_not_available, f"Platform {code} is not available")
    res = await db.execute(
        select(PlatformSettings)
        .where(PlatformSettings.platform_code == code, PlatformSettings.status == "published")
        .order_by(PlatformSettings.version.desc())
    )
    ver = res.scalars().first()
    if ver is None:
        raise ApiError(ErrorCode.settings_not_published, f"Platform {code} has no published settings")
    return {
        "code": platform.code,
        "name": platform.name,
        "status": platform.status,
        "version": ver.version,
        "global": ver.global_config,
        "markets": ver.markets,
        "sources": ver.sources,
    }


async def published_category(db: AsyncSession, code: str) -> dict[str, Any]:
    res = await db.execute(
        select(CategoryTemplate)
        .where(CategoryTemplate.code == code, CategoryTemplate.status == "published")
        .order_by(CategoryTemplate.version.desc())
    )
    row = res.scalars().first()
    if row is None:
        raise ApiError(ErrorCode.category_not_found, f"Category {code} is not available")
    return row.as_dict()


async def published_scenarios(db: AsyncSession) -> list[dict[str, Any]]:
    res = await db.execute(
        select(Scenario)
        .where(Scenario.status == "published")
        .order_by(Scenario.code, Scenario.version.desc())
    )
    seen: set[str] = set()
    rows = []
    for s in res.scalars().all():
        if s.code in seen:
            continue
        seen.add(s.code)
        rows.append(scenario_dict(s))
    return rows


async def published_weights(db: AsyncSession) -> dict[str, Any]:
    res = await db.execute(
        select(WeightSet).where(WeightSet.status == "published").order_by(WeightSet.version.desc())
    )
    row = res.scalars().first()
    if row is None:
        raise ApiError(ErrorCode.settings_not_published, "No published weight set")
    return {"version": row.version, "behavior": row.behavior, "score_by_goal": row.score_by_goal}


def scenario_dict(s: Scenario) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "code": s.code,
        "name": s.name,
        "version": s.version,
        "modifiers": s.modifiers,
        "country_codes": list(s.country_codes or []),
        "category_codes": list(s.category_codes or []),
        "date_rules": s.date_rules,
        "weight": float(s.weight),
        "active": bool(s.active),
        "status": s.status,
        "description": (s.modifiers or {}).get("description", ""),
    }


async def tier_dict(db: AsyncSession, code: str) -> dict[str, Any]:
    tier = await db.get(Tier, code)
    if tier is None:
        raise ApiError(ErrorCode.validation_error, f"Unknown tier {code}")
    return {
        "code": tier.code,
        "runs_target": tier.runs_target,
        "min_runs": tier.min_runs,
        "scenarios": tier.scenarios,
        "max_audiences": tier.max_audiences,
        "agents": tier.agents,
        "archetypes": tier.archetypes,
    }


# --------------------------------------------------------------------------- draft loaders (sandbox)


async def latest_country(db: AsyncSession, code: str, prefer_draft: bool) -> dict[str, Any]:
    if not prefer_draft:
        return await published_country(db, code)
    country = await db.get(Country, code.upper())
    if country is None:
        raise ApiError(ErrorCode.country_not_active, f"Country {code} does not exist")
    res = await db.execute(
        select(CountryVersion)
        .where(CountryVersion.country_code == country.code, CountryVersion.status == "draft")
        .order_by(CountryVersion.version.desc())
    )
    ver = res.scalars().first()
    if ver is None:
        return await published_country(db, code)
    return {
        "code": country.code,
        "name": country.name,
        "currency": country.currency,
        "payment_methods": list(country.payment_methods),
        "version": ver.version,
        "data": ver.data,
        "sources": ver.sources,
        "draft": True,
    }


async def latest_platform(db: AsyncSession, code: str, prefer_draft: bool) -> dict[str, Any]:
    if not prefer_draft:
        return await published_platform(db, code)
    platform = await db.get(Platform, code)
    if platform is None:
        raise ApiError(ErrorCode.platform_not_available, f"Platform {code} does not exist")
    res = await db.execute(
        select(PlatformSettings)
        .where(PlatformSettings.platform_code == code, PlatformSettings.status == "draft")
        .order_by(PlatformSettings.version.desc())
    )
    ver = res.scalars().first()
    if ver is None:
        return await published_platform(db, code)
    return {
        "code": platform.code,
        "name": platform.name,
        "status": platform.status,
        "version": ver.version,
        "global": ver.global_config,
        "markets": ver.markets,
        "sources": ver.sources,
        "draft": True,
    }


async def latest_category(db: AsyncSession, code: str, prefer_draft: bool) -> dict[str, Any]:
    if prefer_draft:
        res = await db.execute(
            select(CategoryTemplate)
            .where(CategoryTemplate.code == code, CategoryTemplate.status == "draft")
            .order_by(CategoryTemplate.version.desc())
        )
        row = res.scalars().first()
        if row is not None:
            d = row.as_dict()
            d["draft"] = True
            return d
    return await published_category(db, code)


async def latest_scenarios(db: AsyncSession, prefer_draft: bool) -> list[dict[str, Any]]:
    if not prefer_draft:
        return await published_scenarios(db)
    res = await db.execute(
        select(Scenario)
        .where(Scenario.status.in_(["draft", "published"]))
        .order_by(Scenario.code, Scenario.version.desc())
    )
    seen: set[str] = set()
    rows = []
    for s in res.scalars().all():
        if s.code in seen:
            continue
        seen.add(s.code)
        d = scenario_dict(s)
        d["status"] = "published"  # the resolver only accepts published rows; for the sandbox drafts count
        rows.append(d)
    return rows


async def latest_weights(db: AsyncSession, prefer_draft: bool) -> dict[str, Any]:
    if prefer_draft:
        res = await db.execute(
            select(WeightSet).where(WeightSet.status == "draft").order_by(WeightSet.version.desc())
        )
        row = res.scalars().first()
        if row is not None:
            return {
                "version": row.version,
                "behavior": row.behavior,
                "score_by_goal": row.score_by_goal,
                "draft": True,
            }
    return await published_weights(db)


# --------------------------------------------------------------------------- resolver entry point


async def resolve_for_test(
    db: AsyncSession,
    *,
    test: dict[str, Any],
    country_code: str,
    category_code: str,
    tier_code: str,
    profile: dict[str, Any] | None,
    use_drafts: bool = False,
    tier_override: dict[str, Any] | None = None,
    today: date | None = None,
) -> FrozenConfig:
    country = await latest_country(db, country_code, use_drafts)
    category = await latest_category(db, category_code, use_drafts)
    platforms = {}
    for p in test.get("platforms", []):
        platforms[p["code"]] = await latest_platform(db, p["code"], use_drafts)
    scenarios = await latest_scenarios(db, use_drafts)
    weights = await latest_weights(db, use_drafts)
    tier = await tier_dict(db, tier_code)
    if tier_override:
        tier.update(tier_override)
    app_settings = await settings_service.get_all(db)
    return resolve(
        country=country,
        platforms=platforms,
        category=category,
        scenarios=scenarios,
        weights=weights,
        test=test,
        tier=tier,
        profile=profile or {},
        settings=app_settings,
        today=today,
    )


# --------------------------------------------------------------------------- versions API


def _version_out(kind: str, row: Any, code: str | None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": str(row.id),
        "code": code,
        "version": int(row.version),
        "status": row.status,
        "change_note": row.change_note,
        "created_by": row.created_by,
        "published_at": row.published_at,
        "created_at": row.created_at,
        "data": data,
    }


async def list_versions(
    db: AsyncSession, kind: str, code: str | None = None, with_data: bool = False
) -> list[dict[str, Any]]:
    _check_kind(kind)
    if kind == "countries":
        stmt = select(CountryVersion).order_by(CountryVersion.country_code, CountryVersion.version.desc())
        if code:
            stmt = stmt.where(CountryVersion.country_code == code.upper())
        rows = (await db.execute(stmt)).scalars().all()
        return [_version_out(kind, r, r.country_code, r.data if with_data else None) for r in rows]
    if kind == "platforms":
        stmt = select(PlatformSettings).order_by(
            PlatformSettings.platform_code, PlatformSettings.version.desc()
        )
        if code:
            stmt = stmt.where(PlatformSettings.platform_code == code)
        rows = (await db.execute(stmt)).scalars().all()
        return [
            _version_out(
                kind,
                r,
                r.platform_code,
                {"global": r.global_config, "markets": r.markets, "sources": r.sources}
                if with_data
                else None,
            )
            for r in rows
        ]
    if kind == "categories":
        stmt = select(CategoryTemplate).order_by(CategoryTemplate.code, CategoryTemplate.version.desc())
        if code:
            stmt = stmt.where(CategoryTemplate.code == code)
        rows = (await db.execute(stmt)).scalars().all()
        return [_version_out(kind, r, r.code, r.as_dict() if with_data else None) for r in rows]
    if kind == "scenarios":
        stmt = select(Scenario).order_by(Scenario.code, Scenario.version.desc())
        if code:
            stmt = stmt.where(Scenario.code == code)
        rows = (await db.execute(stmt)).scalars().all()
        return [_version_out(kind, r, r.code, scenario_dict(r) if with_data else None) for r in rows]
    rows = (await db.execute(select(WeightSet).order_by(WeightSet.version.desc()))).scalars().all()
    return [
        _version_out(
            kind, r, None, {"behavior": r.behavior, "score_by_goal": r.score_by_goal} if with_data else None
        )
        for r in rows
    ]


def _check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ApiError(
            ErrorCode.validation_error, f"Unknown settings kind '{kind}'", details={"kinds": list(KINDS)}
        )


async def _next_version(db: AsyncSession, kind: str, code: str | None) -> int:
    if kind == "countries":
        res = await db.execute(
            select(CountryVersion.version)
            .where(CountryVersion.country_code == code)
            .order_by(CountryVersion.version.desc())
            .limit(1)
        )
    elif kind == "platforms":
        res = await db.execute(
            select(PlatformSettings.version)
            .where(PlatformSettings.platform_code == code)
            .order_by(PlatformSettings.version.desc())
            .limit(1)
        )
    elif kind == "categories":
        res = await db.execute(
            select(CategoryTemplate.version)
            .where(CategoryTemplate.code == code)
            .order_by(CategoryTemplate.version.desc())
            .limit(1)
        )
    elif kind == "scenarios":
        res = await db.execute(
            select(Scenario.version).where(Scenario.code == code).order_by(Scenario.version.desc()).limit(1)
        )
    else:
        res = await db.execute(select(WeightSet.version).order_by(WeightSet.version.desc()).limit(1))
    row = res.first()
    return (int(row[0]) + 1) if row else 1


async def _get_row(db: AsyncSession, kind: str, row_id: str) -> Any:
    model = {
        "countries": CountryVersion,
        "platforms": PlatformSettings,
        "categories": CategoryTemplate,
        "scenarios": Scenario,
        "weights": WeightSet,
    }[kind]
    try:
        rid = uuid.UUID(str(row_id))
    except ValueError:
        raise ApiError(ErrorCode.not_found, f"{kind} version {row_id} not found")
    row = await db.get(model, rid)
    if row is None:
        raise ApiError(ErrorCode.not_found, f"{kind} version {row_id} not found")
    return row


def _code_of(kind: str, row: Any) -> str | None:
    if kind == "countries":
        return row.country_code
    if kind == "platforms":
        return row.platform_code
    if kind in ("categories", "scenarios"):
        return row.code
    return None


async def create_draft(
    db: AsyncSession, kind: str, payload: dict[str, Any], actor_id: uuid.UUID | None, ip: str | None = None
) -> dict[str, Any]:
    """Create a new draft version. For countries/platforms the parent row is created when missing."""
    _check_kind(kind)
    code = (payload.get("code") or "").strip()
    data = dict(payload.get("data") or {})
    note = str(payload.get("change_note") or "")
    now = now_utc()
    if kind == "countries":
        code = code.upper()
        if len(code) != 2:
            raise ApiError(ErrorCode.validation_error, "Country code must be 2 letters")
        country = await db.get(Country, code)
        if country is None:
            country = Country(
                code=code,
                name=payload.get("name") or code,
                currency=(payload.get("currency") or data.get("currency") or "USD").upper(),
                payment_methods=list(
                    payload.get("payment_methods") or data.get("payment_methods") or ["card"]
                ),
                active=bool(payload.get("active", True)),
            )
            db.add(country)
        else:
            if payload.get("name"):
                country.name = payload["name"]
            if payload.get("currency"):
                country.currency = payload["currency"].upper()
            if payload.get("payment_methods") is not None:
                country.payment_methods = list(payload["payment_methods"])
            if payload.get("active") is not None:
                country.active = bool(payload["active"])
        row = CountryVersion(
            country_code=code,
            version=await _next_version(db, kind, code),
            data=data,
            sources=dict(payload.get("sources") or data.get("sources") or {}),
            change_note=note,
            status="draft",
            created_by=actor_id,
        )
    elif kind == "platforms":
        if not code:
            raise ApiError(ErrorCode.validation_error, "Platform code required")
        platform = await db.get(Platform, code)
        if platform is None:
            platform = Platform(
                code=code,
                name=payload.get("name") or code.title(),
                status=payload.get("platform_status") or payload.get("status") or "planned",
                active=bool(payload.get("active", True)),
            )
            db.add(platform)
        else:
            if payload.get("name"):
                platform.name = payload["name"]
            st = payload.get("platform_status") or payload.get("status")
            if st in ("full", "beta", "planned"):
                platform.status = st
            if payload.get("active") is not None:
                platform.active = bool(payload["active"])
        row = PlatformSettings(
            platform_code=code,
            version=await _next_version(db, kind, code),
            global_config=dict(data.get("global") or payload.get("global") or {}),
            markets=dict(data.get("markets") or payload.get("markets") or {}),
            sources=dict(data.get("sources") or payload.get("sources") or {}),
            change_note=note,
            status="draft",
            created_by=actor_id,
        )
    elif kind == "categories":
        if not code:
            raise ApiError(ErrorCode.validation_error, "Category code required")
        validate_category_data(data)
        row = CategoryTemplate(
            code=code,
            name=payload.get("name") or data.get("name") or code,
            version=await _next_version(db, kind, code),
            status="draft",
            change_note=note,
            created_by=actor_id,
            active=True,
        )
        _apply_category_fields(row, data)
    elif kind == "scenarios":
        if not code:
            raise ApiError(ErrorCode.validation_error, "Scenario code required")
        row = Scenario(
            code=code,
            name=payload.get("name") or data.get("name") or code,
            version=await _next_version(db, kind, code),
            status="draft",
            change_note=note,
            created_by=actor_id,
        )
        _apply_scenario_fields(row, data)
    else:
        row = WeightSet(
            version=await _next_version(db, kind, None),
            behavior=dict(data.get("behavior") or {}),
            score_by_goal=dict(data.get("score_by_goal") or {}),
            status="draft",
            change_note=note,
            created_by=actor_id,
        )
    db.add(row)
    await db.flush()
    await audit.log(
        db,
        actor_id=actor_id,
        action=f"settings.{kind}.create_draft",
        entity=f"settings:{kind}",
        entity_id=row.id,
        data={"code": code, "version": row.version, "change_note": note},
        ip=ip,
    )
    _ = now
    return _version_out(kind, row, _code_of(kind, row), await version_data(db, kind, row))


async def update_version(
    db: AsyncSession,
    kind: str,
    row_id: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Edit a draft in place. Editing a published version creates a new draft from it (published versions are immutable)."""
    _check_kind(kind)
    row = await _get_row(db, kind, row_id)
    data = dict(payload.get("data") or {})
    note = str(payload.get("change_note") or row.change_note)
    if row.status != "draft":
        new_payload = {
            "code": _code_of(kind, row),
            "name": payload.get("name"),
            "data": data,
            "change_note": note,
        }
        return await create_draft(db, kind, new_payload, actor_id, ip)
    if kind == "countries":
        row.data = data
        if payload.get("sources") is not None:
            row.sources = dict(payload["sources"])
    elif kind == "platforms":
        if "global" in data or payload.get("global") is not None:
            row.global_config = dict(data.get("global") or payload.get("global") or {})
        if "markets" in data or payload.get("markets") is not None:
            row.markets = dict(data.get("markets") or payload.get("markets") or {})
        if "sources" in data or payload.get("sources") is not None:
            row.sources = dict(data.get("sources") or payload.get("sources") or {})
    elif kind == "categories":
        validate_category_data(data)
        if payload.get("name"):
            row.name = payload["name"]
        _apply_category_fields(row, data)
    elif kind == "scenarios":
        if payload.get("name"):
            row.name = payload["name"]
        _apply_scenario_fields(row, data)
    else:
        if "behavior" in data:
            row.behavior = dict(data["behavior"])
        if "score_by_goal" in data:
            row.score_by_goal = dict(data["score_by_goal"])
    row.change_note = note
    await db.flush()
    await audit.log(
        db,
        actor_id=actor_id,
        action=f"settings.{kind}.update_draft",
        entity=f"settings:{kind}",
        entity_id=row.id,
        data={"version": row.version, "change_note": note},
        ip=ip,
    )
    return _version_out(kind, row, _code_of(kind, row), await version_data(db, kind, row))


async def publish(
    db: AsyncSession,
    kind: str,
    row_id: str,
    change_note: str,
    actor_id: uuid.UUID | None,
    ip: str | None = None,
) -> dict[str, Any]:
    _check_kind(kind)
    row = await _get_row(db, kind, row_id)
    if row.status == "published":
        return _version_out(kind, row, _code_of(kind, row), await version_data(db, kind, row))
    if row.status != "draft":
        raise ApiError(
            ErrorCode.settings_not_draft,
            "Only draft versions can be published (use rollback for archived ones)",
        )
    if kind == "categories":
        validate_category_data(row.as_dict())
    await _archive_current(db, kind, _code_of(kind, row), except_id=row.id)
    row.status = "published"
    row.published_at = now_utc()
    if change_note:
        row.change_note = change_note
    await _set_current(db, kind, row)
    await db.flush()
    await audit.log(
        db,
        actor_id=actor_id,
        action=f"settings.{kind}.publish",
        entity=f"settings:{kind}",
        entity_id=row.id,
        data={"code": _code_of(kind, row), "version": row.version, "change_note": row.change_note},
        ip=ip,
    )
    return _version_out(kind, row, _code_of(kind, row), await version_data(db, kind, row))


async def rollback(
    db: AsyncSession,
    kind: str,
    row_id_or_code: str,
    to_version: int | None,
    change_note: str,
    actor_id: uuid.UUID | None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Re-publish an earlier version (default: the most recent archived one) and archive the current one."""
    _check_kind(kind)
    code: str | None
    try:
        row = await _get_row(db, kind, row_id_or_code)
        code = _code_of(kind, row)
        if to_version is None and row.status == "archived":
            to_version = row.version
    except ApiError:
        code = row_id_or_code.upper() if kind == "countries" else row_id_or_code
        if kind == "weights":
            code = None
    model = {
        "countries": CountryVersion,
        "platforms": PlatformSettings,
        "categories": CategoryTemplate,
        "scenarios": Scenario,
        "weights": WeightSet,
    }[kind]
    code_col = {
        "countries": "country_code",
        "platforms": "platform_code",
        "categories": "code",
        "scenarios": "code",
        "weights": None,
    }[kind]
    stmt = select(model)
    if code_col:
        stmt = stmt.where(getattr(model, code_col) == code)
    if to_version is not None:
        stmt = stmt.where(model.version == int(to_version))
    else:
        stmt = stmt.where(model.status == "archived")
    stmt = stmt.order_by(model.version.desc())
    target = (await db.execute(stmt)).scalars().first()
    if target is None:
        raise ApiError(
            ErrorCode.settings_version_invalid,
            "No earlier version to roll back to",
            details={"code": code, "to_version": to_version},
        )
    if target.status == "published":
        return _version_out(kind, target, code, await version_data(db, kind, target))
    await _archive_current(db, kind, code, except_id=target.id)
    target.status = "published"
    target.published_at = now_utc()
    if change_note:
        target.change_note = f"{target.change_note} | rollback: {change_note}".strip(" |")
    await _set_current(db, kind, target)
    await db.flush()
    await audit.log(
        db,
        actor_id=actor_id,
        action=f"settings.{kind}.rollback",
        entity=f"settings:{kind}",
        entity_id=target.id,
        data={"code": code, "version": target.version, "change_note": change_note},
        ip=ip,
    )
    return _version_out(kind, target, code, await version_data(db, kind, target))


async def _archive_current(db: AsyncSession, kind: str, code: str | None, except_id: uuid.UUID) -> None:
    model = {
        "countries": CountryVersion,
        "platforms": PlatformSettings,
        "categories": CategoryTemplate,
        "scenarios": Scenario,
        "weights": WeightSet,
    }[kind]
    code_col = {
        "countries": "country_code",
        "platforms": "platform_code",
        "categories": "code",
        "scenarios": "code",
        "weights": None,
    }[kind]
    stmt = select(model).where(model.status == "published", model.id != except_id)
    if code_col:
        stmt = stmt.where(getattr(model, code_col) == code)
    for r in (await db.execute(stmt)).scalars().all():
        r.status = "archived"


async def _set_current(db: AsyncSession, kind: str, row: Any) -> None:
    if kind == "countries":
        country = await db.get(Country, row.country_code)
        if country is not None:
            country.current_version = row.version
    elif kind == "platforms":
        platform = await db.get(Platform, row.platform_code)
        if platform is not None:
            platform.current_version = row.version


async def version_data(db: AsyncSession, kind: str, row: Any) -> dict[str, Any]:
    if kind == "countries":
        return dict(row.data)
    if kind == "platforms":
        return {"global": row.global_config, "markets": row.markets, "sources": row.sources}
    if kind == "categories":
        return row.as_dict()
    if kind == "scenarios":
        return scenario_dict(row)
    return {"behavior": row.behavior, "score_by_goal": row.score_by_goal}


def _apply_category_fields(row: CategoryTemplate, data: dict[str, Any]) -> None:
    for f in CATEGORY_FIELDS:
        if f in data:
            setattr(row, f, data[f])
    if "name" in data and data["name"]:
        row.name = data["name"]


def _apply_scenario_fields(row: Scenario, data: dict[str, Any]) -> None:
    if "modifiers" in data:
        mods = dict(data["modifiers"] or {})
        if data.get("description"):
            mods["description"] = data["description"]
        row.modifiers = mods
    for f in ("country_codes", "category_codes"):
        if f in data:
            setattr(row, f, [str(x) for x in (data[f] or [])])
    if "date_rules" in data:
        row.date_rules = dict(data["date_rules"] or {})
    if "weight" in data:
        row.weight = float(data["weight"])
    if "active" in data:
        row.active = bool(data["active"])


QUESTION_TYPES = ("text", "number", "select", "multiselect", "boolean", "sliders")


def validate_category_data(data: dict[str, Any]) -> None:
    """Structural validation of a category template (questions, trait dimensions)."""
    questions = data.get("questions") or []
    if not isinstance(questions, list):
        raise ApiError(ErrorCode.settings_version_invalid, "questions must be a list")
    keys: set[str] = set()
    for q in questions:
        if not isinstance(q, dict) or not q.get("key") or not q.get("label"):
            raise ApiError(
                ErrorCode.settings_version_invalid,
                "every question needs key and label",
                details={"question": q},
            )
        if q.get("type") not in QUESTION_TYPES:
            raise ApiError(
                ErrorCode.settings_version_invalid,
                f"question {q['key']}: type must be one of {QUESTION_TYPES}",
            )
        if q["type"] in ("select", "multiselect", "sliders") and not q.get("options"):
            raise ApiError(ErrorCode.settings_version_invalid, f"question {q['key']}: options required")
        if q["key"] in keys:
            raise ApiError(ErrorCode.settings_version_invalid, f"duplicate question key {q['key']}")
        keys.add(q["key"])
    for dim in data.get("trait_dimensions") or []:
        if (
            not isinstance(dim, dict)
            or not dim.get("key")
            or dim.get("kind") not in ("vector", "categorical", "reputation")
        ):
            raise ApiError(
                ErrorCode.settings_version_invalid,
                "trait dimension needs key and kind (vector|categorical|reputation)",
                details={"dimension": dim},
            )
    for name, mix in (data.get("default_mixes") or {}).items():
        if not isinstance(mix, dict):
            raise ApiError(ErrorCode.settings_version_invalid, f"default mix {name} must be an object")
