"""Model -> response-schema conversion helpers shared by routers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdAsset, AdTest, Country, Payment, Platform, Report, User
from app.services import auth_service, storage
from app.services.test_state import CANCEL_WINDOW_STAGES
from app.workers.progress import STAGE_LABELS


async def me_out(db: AsyncSession, user: User) -> dict[str, Any]:
    available, enabled = await auth_service.trial_available(db, user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "email_verified": user.email_verified_at is not None,
        "locale": user.locale,
        "country": user.country,
        "trial_available": available,
        "trial_enabled": enabled,
        "created_at": user.created_at,
    }


async def asset_out(asset: AdAsset, with_url: bool = True) -> dict[str, Any]:
    url = None
    if with_url:
        url = await storage.get_storage().presigned_url(asset.storage_key)
    return {
        "id": asset.id,
        "kind": asset.kind,
        "mime": asset.mime,
        "width": asset.width,
        "height": asset.height,
        "duration_s": asset.duration_s,
        "size_bytes": asset.size_bytes,
        "sha256": asset.sha256,
        "url": url,
        "created_at": asset.created_at,
    }


def cancel_window(test: AdTest) -> bool:
    if test.status == "queued":
        return True
    return (
        test.status == "running"
        and bool(test.cancel_window_open)
        and (test.stage is None or test.stage in CANCEL_WINDOW_STAGES)
    )


async def test_out(db: AsyncSession, test: AdTest, with_urls: bool = True) -> dict[str, Any]:
    assets = (
        (
            await db.execute(
                select(AdAsset)
                .where(AdAsset.ad_test_id == test.id, AdAsset.kind.in_(["image", "video"]))
                .order_by(AdAsset.created_at)
            )
        )
        .scalars()
        .all()
    )
    names = {p.code: p.name for p in (await db.execute(select(Platform))).scalars().all()}
    snapshot = test.profile_snapshot or {}
    return {
        "id": test.id,
        "title": test.title,
        "status": test.status,
        "tier_code": test.tier_code,
        "country_code": test.country_code,
        "post_type": test.post_type,
        "goal": test.goal,
        "budget_minor": test.budget_minor,
        "currency": test.currency,
        "schedule": test.schedule or {},
        "platforms": [
            {
                "code": p["code"],
                "name": names.get(p["code"]),
                "placements": p.get("placements", []),
                "budget_share": float(p.get("budget_share", 0)),
                "settings_version": p.get("settings_version"),
            }
            for p in (test.platforms or [])
        ],
        "audiences": test.audiences or [],
        "ad_copy": test.ad_copy or {},
        "assets": [await asset_out(a, with_urls) for a in assets],
        "profile": {
            "profile_id": test.profile_id,
            "preset_name": snapshot.get("_preset_name"),
            "version": snapshot.get("_preset_version"),
            "mode": test.profile_mode,
            "snapshot": {k: v for k, v in snapshot.items() if not k.startswith("_")} or None,
        },
        "settings_versions": test.settings_versions or {},
        "cancel_window": cancel_window(test),
        "cancel_count": test.cancel_count,
        "free_restart_available": test.free_restart_available,
        "rerun_available": test.rerun_available,
        "paid_via": test.paid_via,
        "progress": {
            "pct": test.progress_pct,
            "stage": test.stage,
            "label": STAGE_LABELS.get(test.stage or "", None),
        },
        "score": test.score,
        "error": test.error,
        "fingerprint": test.fingerprint,
        "engine_version": test.engine_version,
        "parent_test_id": test.parent_test_id,
        "created_at": test.created_at,
        "updated_at": test.updated_at,
        "confirmed_at": test.confirmed_at,
        "queued_at": test.queued_at,
        "started_at": test.started_at,
        "finished_at": test.finished_at,
    }


def test_list_item(test: AdTest) -> dict[str, Any]:
    return {
        "id": test.id,
        "title": test.title,
        "status": test.status,
        "tier_code": test.tier_code,
        "country_code": test.country_code,
        "post_type": test.post_type,
        "goal": test.goal,
        "platforms": [p["code"] for p in (test.platforms or [])],
        "progress_pct": test.progress_pct,
        "score": test.score,
        "created_at": test.created_at,
        "finished_at": test.finished_at,
    }


def payment_out(p: Payment) -> dict[str, Any]:
    return {
        "id": p.id,
        "ad_test_id": p.ad_test_id,
        "method": p.method,
        "mode": p.mode,
        "status": p.status,
        "amount_usd_minor": p.amount_usd_minor,
        "currency": p.currency,
        "local_currency": p.local_currency,
        "local_amount_minor": p.local_amount_minor,
        "fx_rate": float(p.fx_rate) if p.fx_rate is not None else None,
        "payment_code": p.payment_code,
        "checkout_url": p.checkout_url,
        "admin_reference": p.admin_reference,
        "cancel_reason": p.cancel_reason,
        "expires_at": p.expires_at,
        "paid_at": p.paid_at,
        "refunded_at": p.refunded_at,
        "created_at": p.created_at,
    }


async def admin_payment_out(db: AsyncSession, p: Payment) -> dict[str, Any]:
    base = payment_out(p)
    user = await db.get(User, p.user_id)
    test = await db.get(AdTest, p.ad_test_id)
    base.update(
        {
            "user_id": p.user_id,
            "user_email": user.email if user else None,
            "test_title": test.title if test else None,
            "tier_code": p.tier_code,
            "platform_count": p.platform_count,
            "approved_by": p.approved_by,
            "approved_at": p.approved_at,
            "refund_ref": p.refund_ref,
            "flagged": p.flagged,
            "stripe_session_id": p.stripe_session_id,
            "stripe_payment_intent_id": p.stripe_payment_intent_id,
        }
    )
    return base


def report_out(test: AdTest, report: Report) -> dict[str, Any]:
    summary = dict(report.summary or {})
    headline = summary.pop("headline_metric", {}) or {}
    summary.pop("meta", None)
    return {
        "test_id": test.id,
        "title": test.title,
        "goal": test.goal,
        "post_type": test.post_type,
        "headline_metric": headline,
        "score": test.score,
        "summary": summary,
        "funnel": report.funnel or {},
        "segments": report.segments or {},
        "brand_relationship": report.brand_relationship or {},
        "timing": report.timing or {},
        "comments": [
            {
                "archetype": c.get("archetype", ""),
                "text": c.get("text", ""),
                "topic": c.get("topic"),
                "sentiment": float(c.get("sentiment", 0.0)),
                "language_group": c.get("language_group", "en"),
                "platform": c.get("platform", ""),
                "scenario": c.get("scenario", ""),
            }
            for c in (report.comments or [])
        ],
        "reasons": [
            {
                "section": r.get("section", "general"),
                "statement": r.get("statement", ""),
                "evidence_ids": r.get("evidence_ids", []),
                "confidence": float(r.get("confidence", 0.5)),
            }
            for r in (report.reasons or [])
        ],
        "evidence": [
            {
                "id": e.get("id"),
                "type": e.get("type"),
                "statement": e.get("statement"),
                "values": e.get("values", {}),
                "platform": e.get("platform"),
                "audience_idx": e.get("audience_idx"),
            }
            for e in (report.evidence or [])
        ],
        "audiences": report.audiences or [],
        "platforms": report.platforms or [],
        "language_groups": report.language_groups or [],
        "settings_versions": test.settings_versions or {},
        "engine_version": test.engine_version,
        "note": report.note,
        "pdf_available": bool(report.pdf_key),
        "created_at": report.created_at,
    }


async def country_out(
    db: AsyncSession, country: Country, version_data: dict[str, Any] | None, version: int | None
) -> dict[str, Any]:
    data = version_data or {}
    groups = []
    for g in data.get("language_groups", []) or []:
        groups.append(
            {
                "code": g.get("code"),
                "name": g.get("name", g.get("code")),
                "share": float(g.get("share", 0)),
                "reading_languages": list(g.get("reading_languages", [])),
                "source": g.get("source"),
            }
        )
    return {
        "code": country.code,
        "name": country.name,
        "currency": country.currency,
        "payment_methods": list(country.payment_methods or []),
        "languages": list(data.get("languages", [])),
        "language_groups": groups,
        "version": version,
        "active": country.active,
    }
