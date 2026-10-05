"""Ad tests: create, edit, list, assets, platform selection, post settings, duplicate, delete."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import AdAsset, AdTest, Country, Platform, Tier, User
from app.security import now_utc
from app.services import media, settings_service, settings_versions, storage, test_state
from app.services.test_state import EDITABLE


async def get_owned(db: AsyncSession, user: User, test_id: uuid.UUID, for_update: bool = False) -> AdTest:
    if for_update:
        res = await db.execute(select(AdTest).where(AdTest.id == test_id).with_for_update())
        test = res.scalar_one_or_none()
    else:
        test = await db.get(AdTest, test_id)
    if test is None or (test.user_id != user.id and not user.is_admin):
        raise ApiError(ErrorCode.not_found, "Test not found")
    return test


def ensure_editable(test: AdTest) -> None:
    if test.status not in EDITABLE:
        raise ApiError(
            ErrorCode.test_not_editable,
            f"Test can only be edited while it is a draft (status: {test.status})",
            details={"status": test.status},
        )


def _back_to_draft(test: AdTest) -> None:
    """Any edit after confirm invalidates the confirmation: awaiting_payment -> draft."""
    if test.status == "awaiting_payment":
        test_state.transition(test, "draft")
    test.fingerprint = None
    test.fingerprint_payload = None
    test.confirmed_at = None


async def create(
    db: AsyncSession,
    user: User,
    *,
    title: str,
    country_code: str,
    tier_code: str,
    ad_copy: dict[str, Any],
    audiences: list[dict[str, Any]],
) -> AdTest:
    country = await db.get(Country, country_code.upper())
    if country is None or not country.active:
        raise ApiError(ErrorCode.country_not_active, f"Country {country_code} is not available")
    tier = await db.get(Tier, tier_code)
    if tier is None or not tier.active:
        raise ApiError(ErrorCode.validation_error, f"Unknown tier {tier_code}")
    if len(audiences) > tier.max_audiences:
        raise ApiError(
            ErrorCode.audience_invalid, f"Tier {tier.code} allows up to {tier.max_audiences} audience(s)"
        )
    test = AdTest(
        user_id=user.id,
        title=title.strip() or "Untitled test",
        status="draft",
        tier_code=tier.code,
        country_code=country.code,
        currency="USD",
        post_type="paid",
        goal="sales",
        ad_copy=ad_copy,
        audiences=audiences,
        platforms=[],
        schedule={"days": 3},
        settings_versions={},
    )
    db.add(test)
    await db.flush()
    return test


async def update(db: AsyncSession, user: User, test_id: uuid.UUID, patch: dict[str, Any]) -> AdTest:
    test = await get_owned(db, user, test_id, for_update=True)
    ensure_editable(test)
    if patch.get("title") is not None:
        test.title = patch["title"].strip() or test.title
    if patch.get("tier_code") is not None:
        tier = await db.get(Tier, patch["tier_code"])
        if tier is None or not tier.active:
            raise ApiError(ErrorCode.validation_error, f"Unknown tier {patch['tier_code']}")
        test.tier_code = tier.code
    if patch.get("ad_copy") is not None:
        test.ad_copy = patch["ad_copy"]
    if patch.get("audiences") is not None:
        tier = await db.get(Tier, test.tier_code)
        if tier and len(patch["audiences"]) > tier.max_audiences:
            raise ApiError(
                ErrorCode.audience_invalid, f"Tier {tier.code} allows up to {tier.max_audiences} audience(s)"
            )
        test.audiences = patch["audiences"]
    _back_to_draft(test)
    await db.flush()
    return test


async def delete(db: AsyncSession, user: User, test_id: uuid.UUID) -> None:
    test = await get_owned(db, user, test_id, for_update=True)
    if test.status not in ("draft", "awaiting_payment"):
        raise ApiError(ErrorCode.test_not_editable, "Only drafts can be deleted")
    if test.payment_id is not None:
        raise ApiError(
            ErrorCode.test_not_editable, "This draft is prepaid; restart it instead of deleting it"
        )
    for asset in await assets_for(db, test.id):
        await storage.get_storage().delete(asset.storage_key)
        await db.delete(asset)
    await db.delete(test)
    await db.flush()


async def assets_for(
    db: AsyncSession, test_id: uuid.UUID, kinds: tuple[str, ...] = ("image", "video")
) -> list[AdAsset]:
    res = await db.execute(
        select(AdAsset)
        .where(AdAsset.ad_test_id == test_id, AdAsset.kind.in_(kinds))
        .order_by(AdAsset.created_at)
    )
    return list(res.scalars().all())


async def add_asset(
    db: AsyncSession, user: User, test_id: uuid.UUID, data: bytes, filename: str | None
) -> AdAsset:
    test = await get_owned(db, user, test_id, for_update=True)
    ensure_editable(test)
    existing = await assets_for(db, test.id)
    max_assets = int((await settings_service.get(db, "limits", {})).get("max_assets_per_test", 3))
    if len(existing) >= max_assets:
        raise ApiError(ErrorCode.asset_invalid, f"A test can have at most {max_assets} media files")
    info = await media.process_upload_async(data, filename)
    asset_id = uuid.uuid4()
    key = storage.asset_key(str(test.id), str(asset_id), info.ext)
    await storage.get_storage().put(key, info.data, info.mime)
    asset = AdAsset(
        id=asset_id,
        ad_test_id=test.id,
        kind=info.kind,
        storage_key=key,
        mime=info.mime,
        width=info.width,
        height=info.height,
        duration_s=info.duration_s,
        size_bytes=len(info.data),
        sha256=hashlib.sha256(info.data).hexdigest(),
        meta={**info.meta, "filename": (filename or "")[:200]},
    )
    db.add(asset)
    _back_to_draft(test)
    await db.flush()
    return asset


async def delete_asset(db: AsyncSession, user: User, test_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    test = await get_owned(db, user, test_id, for_update=True)
    ensure_editable(test)
    asset = await db.get(AdAsset, asset_id)
    if asset is None or asset.ad_test_id != test.id:
        raise ApiError(ErrorCode.not_found, "Asset not found")
    st = storage.get_storage()
    await st.delete(asset.storage_key)
    # derived frames/audio
    res = await db.execute(select(AdAsset).where(AdAsset.parent_asset_id == asset.id))
    for child in res.scalars().all():
        await st.delete(child.storage_key)
        await db.delete(child)
    await db.delete(asset)
    _back_to_draft(test)
    await db.flush()


async def set_platforms(
    db: AsyncSession, user: User, test_id: uuid.UUID, selections: list[dict[str, Any]]
) -> AdTest:
    test = await get_owned(db, user, test_id, for_update=True)
    ensure_editable(test)
    if not selections:
        raise ApiError(ErrorCode.validation_error, "Select at least one platform")
    limits = await settings_service.get(db, "limits", {})
    if len(selections) > int(limits.get("max_platforms_per_test", 3)):
        raise ApiError(
            ErrorCode.validation_error,
            f"At most {limits.get('max_platforms_per_test', 3)} platforms per test",
        )
    codes = [s["code"] for s in selections]
    if len(set(codes)) != len(codes):
        raise ApiError(ErrorCode.validation_error, "Each platform can be selected once")
    cleaned = []
    for sel in selections:
        platform = await db.get(Platform, sel["code"])
        if platform is None or not platform.active or platform.status == "planned":
            raise ApiError(
                ErrorCode.platform_not_available,
                f"Platform {sel['code']} is not available yet",
                details={"code": sel["code"]},
            )
        published = await settings_versions.published_platform(db, platform.code)
        known = set((published.get("global") or {}).get("placements", {}).keys())
        placements = [p for p in sel.get("placements") or []]
        unknown = [p for p in placements if known and p not in known]
        if unknown:
            raise ApiError(
                ErrorCode.validation_error,
                f"Unknown placements for {platform.code}: {unknown}",
                details={"allowed": sorted(known)},
            )
        if not placements and known:
            placements = [sorted(known)[0]] if "feed" not in known else ["feed"]
        cleaned.append(
            {
                "code": platform.code,
                "placements": placements,
                "budget_share": float(sel.get("budget_share", 100.0)),
                "settings_version": published["version"],
            }
        )
    if test.post_type in ("paid", "boosted"):
        _validate_shares(cleaned)
    else:
        for c in cleaned:
            c["budget_share"] = round(100.0 / len(cleaned), 4)
    # goal must be supported on every platform for the current post type
    for c in cleaned:
        published = await settings_versions.published_platform(db, c["code"])
        goals = (published.get("global") or {}).get("supported_goals", {}).get(test.post_type)
        if goals and test.goal not in goals:
            raise ApiError(
                ErrorCode.goal_not_supported,
                f"Goal '{test.goal}' is not supported for {test.post_type} posts on {c['code']}",
                details={"platform": c["code"], "supported_goals": goals},
            )
    test.platforms = cleaned
    _back_to_draft(test)
    await db.flush()
    return test


def _validate_shares(selections: list[dict[str, Any]]) -> None:
    total = sum(float(s.get("budget_share", 0)) for s in selections)
    if abs(total - 100.0) > 0.01:
        raise ApiError(
            ErrorCode.budget_shares_invalid,
            f"Budget shares must add up to 100 (got {total:g})",
            details={"total": total},
        )
    for s in selections:
        if float(s.get("budget_share", 0)) <= 0:
            raise ApiError(ErrorCode.budget_shares_invalid, f"Budget share for {s['code']} must be above 0")


async def set_post(
    db: AsyncSession,
    user: User,
    test_id: uuid.UUID,
    *,
    post_type: str,
    goal: str,
    budget_minor: int | None,
    currency: str,
    schedule: dict[str, Any],
) -> AdTest:
    test = await get_owned(db, user, test_id, for_update=True)
    ensure_editable(test)
    limits = await settings_service.get(db, "limits", {})
    if post_type == "organic":
        if budget_minor not in (None, 0):
            raise ApiError(
                ErrorCode.budget_not_allowed,
                "An organic post has no budget",
                details={"budget_minor": budget_minor},
            )
        budget_minor = None
        observe = int(schedule.get("observe_days") or 3)
        if not 1 <= observe <= int(limits.get("max_organic_observe_days", 7)):
            raise ApiError(ErrorCode.schedule_invalid, "Observation window must be 1-7 days")
        post_at = schedule.get("post_at")
        clean_schedule = {
            "post_at": _iso(post_at) if post_at else _iso(now_utc()),
            "observe_days": observe,
            "hours": schedule.get("hours"),
        }
    else:
        if budget_minor is None or int(budget_minor) <= 0:
            raise ApiError(
                ErrorCode.budget_required,
                f"A {post_type} post needs a budget",
                details={"post_type": post_type},
            )
        days = int(schedule.get("days") or 3)
        if not 1 <= days <= int(limits.get("max_schedule_days", 14)):
            raise ApiError(
                ErrorCode.schedule_invalid, "Campaign length must be 1-14 days", details={"days": days}
            )
        start = schedule.get("start_date")
        start_d = _to_date(start) if start else date.today()
        if start_d < date.today():
            raise ApiError(
                ErrorCode.schedule_invalid, "Start date is in the past", details={"start_date": str(start_d)}
            )
        clean_schedule = {"start_date": start_d.isoformat(), "days": days, "hours": schedule.get("hours")}
    # goal support per platform for this post type
    for sel in test.platforms or []:
        published = await settings_versions.published_platform(db, sel["code"])
        goals = (published.get("global") or {}).get("supported_goals", {}).get(post_type)
        if goals and goal not in goals:
            raise ApiError(
                ErrorCode.goal_not_supported,
                f"Goal '{goal}' is not supported for {post_type} posts on {sel['code']}",
                details={"platform": sel["code"], "supported_goals": goals},
            )
    test.post_type = post_type
    test.goal = goal
    test.budget_minor = int(budget_minor) if budget_minor is not None else None
    test.currency = currency.upper()
    test.schedule = clean_schedule
    if post_type == "organic":
        n = max(1, len(test.platforms or []))
        test.platforms = [{**p, "budget_share": round(100.0 / n, 4)} for p in (test.platforms or [])]
    _back_to_draft(test)
    await db.flush()
    return test


def _iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ApiError(ErrorCode.schedule_invalid, "Invalid start date")


async def duplicate(db: AsyncSession, user: User, test_id: uuid.UUID) -> AdTest:
    src = await get_owned(db, user, test_id)
    new = AdTest(
        user_id=user.id,
        title=f"{src.title} (copy)",
        status="draft",
        tier_code=src.tier_code,
        country_code=src.country_code,
        post_type=src.post_type,
        goal=src.goal,
        platforms=[dict(p) for p in (src.platforms or [])],
        schedule=_shift_schedule(src.schedule),
        budget_minor=src.budget_minor,
        currency=src.currency,
        audiences=[dict(a) for a in (src.audiences or [])],
        ad_copy=dict(src.ad_copy or {}),
        profile_id=src.profile_id,
        profile_version_id=src.profile_version_id,
        profile_mode=src.profile_mode,
        profile_snapshot=dict(src.profile_snapshot) if src.profile_snapshot else None,
        parent_test_id=src.id,
        settings_versions={},
    )
    db.add(new)
    await db.flush()
    st = storage.get_storage()
    for asset in await assets_for(db, src.id):
        data = await st.get(asset.storage_key)
        new_id = uuid.uuid4()
        ext = asset.storage_key.rsplit(".", 1)[-1]
        key = storage.asset_key(str(new.id), str(new_id), ext)
        await st.put(key, data, asset.mime)
        db.add(
            AdAsset(
                id=new_id,
                ad_test_id=new.id,
                kind=asset.kind,
                storage_key=key,
                mime=asset.mime,
                width=asset.width,
                height=asset.height,
                duration_s=asset.duration_s,
                size_bytes=asset.size_bytes,
                sha256=asset.sha256,
                meta=dict(asset.meta),
            )
        )
    await db.flush()
    return new


def _shift_schedule(schedule: dict[str, Any] | None) -> dict[str, Any]:
    sched = dict(schedule or {"days": 3})
    if sched.get("start_date"):
        try:
            if date.fromisoformat(str(sched["start_date"])[:10]) < date.today():
                sched["start_date"] = date.today().isoformat()
        except ValueError:
            sched["start_date"] = date.today().isoformat()
    return sched


# --------------------------------------------------------------------------- listing / cursors


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps({"t": created_at.isoformat(), "id": str(row_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        return datetime.fromisoformat(data["t"]), uuid.UUID(data["id"])
    except Exception:  # noqa: BLE001
        raise ApiError(ErrorCode.validation_error, "Invalid cursor")


async def list_tests(
    db: AsyncSession, user: User, cursor: str | None, limit: int = 20, status: str | None = None
) -> tuple[list[AdTest], str | None]:
    stmt = (
        select(AdTest)
        .where(AdTest.user_id == user.id)
        .order_by(AdTest.created_at.desc(), AdTest.id.desc())
        .limit(limit + 1)
    )
    if status:
        stmt = stmt.where(AdTest.status == status)
    cur = decode_cursor(cursor)
    if cur:
        t, rid = cur
        stmt = stmt.where((AdTest.created_at < t) | ((AdTest.created_at == t) & (AdTest.id < rid)))
    rows = list((await db.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)
    return rows, next_cursor
