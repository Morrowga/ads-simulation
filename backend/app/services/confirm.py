"""POST /tests/{id}/confirm: validate inputs, warnings, spec checks, duplicate fingerprint, price."""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, Tier, User
from app.security import now_utc
from app.services import fingerprint as fp
from app.services import fx, pricing, settings_service, settings_versions, test_state, tests_service
from engine.simulation.config.platforms import spec_check
from engine.simulation.config.resolver import build_platform

MESSAGE_CTAS = ("send_message", "message", "whatsapp", "line", "chat")


async def assert_not_duplicate(db: AsyncSession, user: User, test: AdTest) -> None:
    """Checkout and payment are blocked while an identical completed test exists (same engine version)."""
    if not test.fingerprint:
        raise ApiError(ErrorCode.confirm_required, "Confirm the test before checkout")
    res = await db.execute(
        select(AdTest)
        .where(
            AdTest.user_id == user.id,
            AdTest.status == "completed",
            AdTest.fingerprint == test.fingerprint,
            AdTest.id != test.id,
        )
        .order_by(AdTest.finished_at.desc())
    )
    dup = res.scalars().first()
    if dup is not None:
        raise ApiError(
            ErrorCode.duplicate_test,
            "An identical completed test already exists; open its report instead",
            details={"test_id": str(dup.id), "title": dup.title, "score": dup.score},
        )


async def run_confirm(db: AsyncSession, user: User, test_id) -> dict[str, Any]:  # noqa: ANN001
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    test_state.ensure_status(test, "draft", "awaiting_payment")
    assets = await tests_service.assets_for(db, test.id)
    limits = await settings_service.get(db, "limits", {})
    s = get_settings()

    # --- hard validation ---------------------------------------------------------
    errors: list[str] = []
    if not assets:
        errors.append("Upload at least one image or video")
    if not test.platforms:
        errors.append("Select at least one platform")
    if not test.profile_snapshot:
        errors.append("Attach a business profile")
    if test.post_type == "organic" and test.budget_minor is not None:
        errors.append("An organic post cannot have a budget")
    if test.post_type in ("paid", "boosted") and not test.budget_minor:
        errors.append(f"A {test.post_type} post needs a budget")
    if test.post_type in ("paid", "boosted") and test.platforms:
        total = sum(float(p.get("budget_share", 0)) for p in test.platforms)
        if abs(total - 100.0) > 0.01:
            errors.append("Budget shares must add up to 100%")
    sched = test.schedule or {}
    if test.post_type != "organic":
        try:
            start = date.fromisoformat(str(sched.get("start_date") or date.today().isoformat())[:10])
        except ValueError:
            start = date.today()
        if start < date.today():
            errors.append("Start date is in the past")
        if int(sched.get("days") or 0) > int(limits.get("max_schedule_days", 14)):
            errors.append("Campaign length is above 14 days")
    tier = await db.get(Tier, test.tier_code)
    if tier is None:
        errors.append("Unknown tier")
    elif len(test.audiences or []) > tier.max_audiences:
        errors.append(f"Tier {tier.code} allows up to {tier.max_audiences} audience(s)")
    if errors:
        raise ApiError(ErrorCode.validation_error, "The test is not ready to run", details={"errors": errors})

    # --- resolve settings versions (published only) ---------------------------------
    country = await settings_versions.published_country(db, test.country_code)
    category_code = (test.profile_snapshot or {}).get("_category_code") or "other"
    category = await settings_versions.published_category(db, category_code)
    scenarios = await settings_versions.published_scenarios(db)
    weights = await settings_versions.published_weights(db)
    platform_rows = {}
    platform_cfgs = {}
    new_platforms = []
    for sel in test.platforms:
        published = await settings_versions.published_platform(db, sel["code"])
        platform_rows[sel["code"]] = published
        platform_cfgs[sel["code"]] = build_platform(
            sel["code"],
            published["global"],
            published["markets"],
            test.country_code,
            name=published["name"],
            status=published["status"],
            version=published["version"],
        )
        new_platforms.append({**sel, "settings_version": published["version"]})
    test.platforms = new_platforms
    test.settings_versions = {
        "country": {"code": country["code"], "version": country["version"]},
        "category": {"code": category["code"], "version": category["version"]},
        "platforms": {code: row["version"] for code, row in platform_rows.items()},
        "scenarios": [{"code": r["code"], "version": r["version"]} for r in scenarios],
        "weights": weights["version"],
    }
    test.engine_version = s.ENGINE_VERSION

    # --- warnings and spec checks ---------------------------------------------------
    warnings: list[str] = []
    spec_checks: list[dict[str, Any]] = []
    for sel in test.platforms:
        pc = platform_cfgs[sel["code"]]
        if pc.status == "beta":
            warnings.append(
                f"{pc.name} is in beta: its behaviour values have not been compared with pilot campaigns yet"
            )
        goals = pc.supported_goals.get(test.post_type)
        if goals and test.goal not in goals:
            raise ApiError(
                ErrorCode.goal_not_supported,
                f"Goal '{test.goal}' is not supported for {test.post_type} posts on {pc.name}",
                details={"platform": pc.code, "supported_goals": goals},
            )
        for placement in sel.get("placements") or []:
            for asset in assets:
                ok, msg = spec_check(
                    pc,
                    placement,
                    {
                        "kind": asset.kind,
                        "width": asset.width,
                        "height": asset.height,
                        "duration_s": asset.duration_s,
                    },
                )
                spec_checks.append(
                    {
                        "platform": pc.code,
                        "placement": placement,
                        "asset_id": asset.id,
                        "ok": ok,
                        "message": msg,
                    }
                )
                if not ok:
                    warnings.append(msg)
    profile = test.profile_snapshot or {}
    followers = float(profile.get("followers") or 0)
    if test.post_type == "organic" and followers < float(limits.get("organic_followers_warning", 100)):
        warnings.append(f"Organic reach will be very small: the profile has {int(followers)} followers")
    cta = str((test.ad_copy or {}).get("cta") or "").lower()
    if test.goal == "messages" and cta not in MESSAGE_CTAS:
        warnings.append(
            f"The goal is messages but the call to action is '{cta or 'none'}', not a message button"
        )
    if test.budget_minor:
        res = await db.execute(
            select(AdTest.budget_minor).where(
                AdTest.user_id == user.id, AdTest.status == "completed", AdTest.budget_minor.is_not(None)
            )
        )
        past = [int(b) for (b,) in res.all() if b]
        if past and test.budget_minor > float(limits.get("budget_warning_multiplier", 3.0)) * median(past):
            warnings.append(
                f"Budget is more than {limits.get('budget_warning_multiplier', 3.0):g}x your usual budget"
            )
    if tier is not None:
        for aud in test.audiences or []:
            size = (aud.get("targeting") or {}).get("audience_size")
            if size and int(size) < tier.agents:
                warnings.append(
                    f"Audience '{aud.get('name', '')}' ({size} people) is smaller than the tier's population; the population is scaled down"
                )
    if test.post_type == "boosted" and followers == 0:
        warnings.append("Boosted post with 0 followers: only the paid part reaches people")

    # --- fingerprint and duplicate check ---------------------------------------------
    digest, payload = fp.fingerprint(test, assets, s.ENGINE_VERSION)
    test.fingerprint = digest
    test.fingerprint_payload = payload
    duplicate = None
    engine_updated = False
    changed: list[str] = []
    dup_res = await db.execute(
        select(AdTest)
        .where(
            AdTest.user_id == user.id,
            AdTest.status == "completed",
            AdTest.fingerprint == digest,
            AdTest.id != test.id,
        )
        .order_by(AdTest.finished_at.desc())
    )
    dup = dup_res.scalars().first()
    if dup is not None:
        duplicate = {
            "is_duplicate": True,
            "test_id": dup.id,
            "title": dup.title,
            "score": dup.score,
            "completed_at": dup.finished_at,
        }
    else:
        # close matches: same media, other fields changed (or same inputs, older engine)
        media_key = payload["media"]
        res = await db.execute(
            select(AdTest)
            .where(
                AdTest.user_id == user.id,
                AdTest.status == "completed",
                AdTest.id != test.id,
                AdTest.fingerprint_payload.is_not(None),
            )
            .order_by(AdTest.finished_at.desc())
            .limit(50)
        )
        for other in res.scalars().all():
            op = other.fingerprint_payload or {}
            if op.get("media") != media_key:
                continue
            diff = fp.changed_fields(op, payload)
            if diff == ["engine version"]:
                engine_updated = True
                duplicate = {
                    "is_duplicate": False,
                    "test_id": other.id,
                    "title": other.title,
                    "score": other.score,
                    "completed_at": other.finished_at,
                }
                warnings.append(
                    f"Engine updated since your last run of this ad ({op.get('engine')} -> {s.ENGINE_VERSION})"
                )
            elif diff and not changed:
                changed = diff
                duplicate = {
                    "is_duplicate": False,
                    "test_id": other.id,
                    "title": other.title,
                    "score": other.score,
                    "completed_at": other.finished_at,
                }
            break

    # --- price -------------------------------------------------------------------------
    price = await pricing.price_for(db, test.tier_code, len(test.platforms), country["currency"])

    if test.status == "draft":
        test_state.transition(test, "awaiting_payment")
    test.confirmed_at = now_utc()
    await db.flush()

    summary = {
        "title": test.title,
        "country": country["name"],
        "country_code": country["code"],
        "tier": test.tier_code,
        "post_type": test.post_type,
        "goal": test.goal,
        "budget": fx.format_money(test.budget_minor, test.currency) if test.budget_minor else None,
        "budget_minor": test.budget_minor,
        "currency": test.currency,
        "schedule": test.schedule,
        "platforms": [
            {
                "code": p["code"],
                "name": platform_cfgs[p["code"]].name,
                "placements": p.get("placements"),
                "budget_share": p.get("budget_share"),
                "settings_version": p.get("settings_version"),
            }
            for p in test.platforms
        ],
        "audiences": [a.get("name") for a in (test.audiences or [])],
        "media": [
            {"id": str(a.id), "kind": a.kind, "size": f"{a.width}x{a.height}", "duration_s": a.duration_s}
            for a in assets
        ],
        "profile": {
            "name": profile.get("_preset_name"),
            "version": profile.get("_preset_version"),
            "mode": test.profile_mode,
            "category": category["name"],
        },
        "settings_versions": test.settings_versions,
        "engine_version": s.ENGINE_VERSION,
        "prepaid": test_state.is_prepaid(test),
    }
    return {
        "summary": summary,
        "warnings": warnings,
        "spec_checks": spec_checks,
        "duplicate": duplicate,
        "changed_fields": changed,
        "engine_updated": engine_updated,
        "price": price,
        "status": test.status,
        "fingerprint": digest,
    }
