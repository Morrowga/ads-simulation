"""Business profiles: presets with immutable versions, validated against the category template."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import AdTest, BusinessProfile, ProfileVersion, User
from app.security import now_utc, sha256_hex
from app.services import settings_versions
from engine.simulation.population.traits import profile_summary
from engine.simulation.config.resolver import build_category


def data_hash(data: dict[str, Any]) -> str:
    return sha256_hex(json.dumps(data, sort_keys=True, separators=(",", ":"), default=str))


def validate_profile_data(template: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise answers against the template's questions. Unknown keys are kept."""
    errors: dict[str, str] = {}
    out = dict(data or {})
    for q in template.get("questions", []):
        key, qtype, required = q["key"], q.get("type", "text"), bool(q.get("required"))
        value = out.get(key)
        if value in (None, "", [], {}):
            if q.get("default") is not None:
                out[key] = q["default"]  # a question with a default is satisfied by it
                continue
            if required:
                errors[key] = "required"
            continue
        options = q.get("options") or []
        if qtype == "number":
            try:
                num = float(value)
            except (TypeError, ValueError):
                errors[key] = "must be a number"
                continue
            if q.get("min") is not None and num < float(q["min"]):
                errors[key] = f"must be >= {q['min']}"
            if q.get("max") is not None and num > float(q["max"]):
                errors[key] = f"must be <= {q['max']}"
            out[key] = num if num != int(num) else int(num)
        elif qtype == "select":
            if options and value not in options:
                errors[key] = f"must be one of {options}"
        elif qtype == "multiselect":
            if not isinstance(value, list):
                errors[key] = "must be a list"
            elif options and any(v not in options for v in value):
                errors[key] = f"values must be in {options}"
        elif qtype == "boolean":
            if not isinstance(value, bool):
                errors[key] = "must be true or false"
        elif qtype == "sliders":
            if not isinstance(value, dict):
                errors[key] = "must be an object of values"
            else:
                lo, hi = float(q.get("min", 0)), float(q.get("max", 1))
                clean = {}
                for opt in options:
                    v = value.get(opt)
                    if v is None:
                        v = (q.get("default") or {}).get(opt, (lo + hi) / 2)
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        errors[key] = f"{opt} must be a number"
                        break
                    clean[opt] = min(max(v, lo), hi)
                out[key] = clean
        elif qtype == "text":
            if not isinstance(value, str):
                out[key] = str(value)
            elif len(value) > 2000:
                errors[key] = "too long"
    if errors:
        raise ApiError(
            ErrorCode.profile_invalid,
            "Profile data does not match the category template",
            details={"fields": errors},
        )
    return out


async def _template(db: AsyncSession, category_code: str) -> dict[str, Any]:
    return await settings_versions.published_category(db, category_code)


async def get_owned(
    db: AsyncSession, user: User, profile_id: uuid.UUID, include_archived: bool = False
) -> BusinessProfile:
    profile = await db.get(BusinessProfile, profile_id)
    if (
        profile is None
        or profile.user_id != user.id
        or (profile.archived_at is not None and not include_archived)
    ):
        raise ApiError(ErrorCode.not_found, "Profile not found")
    return profile


async def current_version(db: AsyncSession, profile: BusinessProfile) -> ProfileVersion:
    res = await db.execute(
        select(ProfileVersion).where(
            ProfileVersion.profile_id == profile.id, ProfileVersion.version == profile.current_version
        )
    )
    ver = res.scalar_one_or_none()
    if ver is None:
        raise ApiError(ErrorCode.internal_error, "Profile version missing")
    return ver


async def list_profiles(db: AsyncSession, user: User) -> list[tuple[BusinessProfile, ProfileVersion]]:
    res = await db.execute(
        select(BusinessProfile)
        .where(BusinessProfile.user_id == user.id, BusinessProfile.archived_at.is_(None))
        .order_by(BusinessProfile.is_default.desc(), BusinessProfile.updated_at.desc())
    )
    out = []
    for p in res.scalars().all():
        out.append((p, await current_version(db, p)))
    return out


async def create(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    category_code: str,
    data: dict[str, Any],
    is_default: bool = False,
) -> tuple[BusinessProfile, ProfileVersion]:
    template = await _template(db, category_code)
    clean = validate_profile_data(template, data)
    if is_default:
        await _clear_default(db, user)
    profile = BusinessProfile(
        user_id=user.id,
        name=name.strip(),
        category_code=category_code,
        current_version=1,
        is_default=is_default,
    )
    db.add(profile)
    await db.flush()
    version = ProfileVersion(profile_id=profile.id, version=1, data=clean, data_hash=data_hash(clean))
    db.add(version)
    await db.flush()
    return profile, version


async def update(
    db: AsyncSession,
    user: User,
    profile_id: uuid.UUID,
    *,
    name: str | None,
    data: dict[str, Any],
    is_default: bool | None,
) -> tuple[BusinessProfile, ProfileVersion]:
    """Save changes as a new version; the old versions are kept and tests keep their snapshots."""
    profile = await get_owned(db, user, profile_id)
    template = await _template(db, profile.category_code)
    clean = validate_profile_data(template, data)
    cur = await current_version(db, profile)
    if name is not None:
        profile.name = name.strip()
    if is_default is not None:
        if is_default:
            await _clear_default(db, user)
        profile.is_default = is_default
    new_hash = data_hash(clean)
    if new_hash == cur.data_hash:
        await db.flush()
        return profile, cur
    version = ProfileVersion(
        profile_id=profile.id, version=profile.current_version + 1, data=clean, data_hash=new_hash
    )
    db.add(version)
    profile.current_version = version.version
    await db.flush()
    return profile, version


async def duplicate(
    db: AsyncSession, user: User, profile_id: uuid.UUID, name: str | None
) -> tuple[BusinessProfile, ProfileVersion]:
    src = await get_owned(db, user, profile_id, include_archived=True)
    cur = await current_version(db, src)
    return await create(
        db,
        user,
        name=name or f"{src.name} (copy)",
        category_code=src.category_code,
        data=dict(cur.data),
        is_default=False,
    )


async def archive(db: AsyncSession, user: User, profile_id: uuid.UUID) -> BusinessProfile:
    profile = await get_owned(db, user, profile_id)
    profile.archived_at = now_utc()
    profile.is_default = False
    await db.flush()
    return profile


async def versions_with_tests(db: AsyncSession, user: User, profile_id: uuid.UUID) -> list[dict[str, Any]]:
    profile = await get_owned(db, user, profile_id, include_archived=True)
    res = await db.execute(
        select(ProfileVersion)
        .where(ProfileVersion.profile_id == profile.id)
        .order_by(ProfileVersion.version.desc())
    )
    versions = list(res.scalars().all())
    tests_res = await db.execute(
        select(AdTest.id, AdTest.title, AdTest.status, AdTest.profile_version_id).where(
            AdTest.profile_id == profile.id
        )
    )
    by_version: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for tid, title, status, pvid in tests_res.all():
        if pvid is not None:
            by_version.setdefault(pvid, []).append({"id": str(tid), "title": title, "status": status})
    return [
        {
            "id": v.id,
            "version": v.version,
            "data": v.data,
            "data_hash": v.data_hash,
            "created_at": v.created_at,
            "tests": by_version.get(v.id, []),
        }
        for v in versions
    ]


async def _clear_default(db: AsyncSession, user: User) -> None:
    res = await db.execute(
        select(BusinessProfile).where(
            BusinessProfile.user_id == user.id, BusinessProfile.is_default.is_(True)
        )
    )
    for p in res.scalars().all():
        p.is_default = False


async def summary_for(db: AsyncSession, profile: BusinessProfile, data: dict[str, Any]) -> str:
    try:
        template = await _template(db, profile.category_code)
        cat = build_category(profile.category_code, template, "XX")
        return profile_summary(data, cat)
    except ApiError:
        return str(data.get("business_name") or profile.name)


async def category_name(db: AsyncSession, code: str) -> str | None:
    try:
        return (await _template(db, code)).get("name")
    except ApiError:
        return None


async def apply_test_profile(
    db: AsyncSession,
    user: User,
    test: AdTest,
    *,
    profile_id: uuid.UUID,
    mode: str,
    changes: dict[str, Any],
    new_preset_name: str | None,
) -> dict[str, Any]:
    """PUT /tests/{id}/profile: the four save modes.

    preset        - use the preset's current version as is
    one_time      - apply `changes` for this test only (snapshot on the test, preset untouched)
    update_preset - apply `changes` and save them as a new preset version
    new_preset    - apply `changes` and save as a new preset (name required)
    """
    profile = await get_owned(db, user, profile_id)
    cur = await current_version(db, profile)
    template = await _template(db, profile.category_code)
    merged = validate_profile_data(template, {**cur.data, **(changes or {})})
    if mode == "preset":
        snapshot, version, target = validate_profile_data(template, dict(cur.data)), cur, profile
        test_mode = "preset"
    elif mode == "one_time":
        snapshot, version, target = merged, cur, profile
        test_mode = "one_time"
    elif mode == "update_preset":
        target, version = await update(db, user, profile.id, name=None, data=merged, is_default=None)
        snapshot, test_mode = dict(version.data), "preset"
    elif mode == "new_preset":
        if not new_preset_name:
            raise ApiError(ErrorCode.validation_error, "new_preset_name is required for mode new_preset")
        target, version = await create(
            db, user, name=new_preset_name, category_code=profile.category_code, data=merged
        )
        snapshot, test_mode = dict(version.data), "preset"
    else:
        raise ApiError(ErrorCode.validation_error, f"Unknown profile mode {mode}")
    test.profile_id = target.id
    test.profile_version_id = version.id
    test.profile_mode = test_mode
    test.profile_snapshot = {
        **snapshot,
        "_category_code": target.category_code,
        "_preset_name": target.name,
        "_preset_version": version.version,
    }
    await db.flush()
    return {
        "profile_id": target.id,
        "preset_name": target.name,
        "version": version.version,
        "mode": test_mode,
        "snapshot": test.profile_snapshot,
    }
