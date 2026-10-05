"""Admin services: tests overview, users, prices, metrics."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, LLMUsage, Payment, Price, TrialGrant, User
from app.security import now_utc
from app.services import audit, queue, test_state, trial
from app.services.redis_client import get_redis
from app.services.tests_service import decode_cursor, encode_cursor
from app.workers.progress import STAGE_LABELS

STAGES = ("prepare", "analyze_ad", "population", "archetypes", "react", "simulate", "explain", "export")


async def _cost_by_test(db: AsyncSession, test_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    if not test_ids:
        return {}
    res = await db.execute(
        select(LLMUsage.ad_test_id, func.coalesce(func.sum(LLMUsage.cost_usd), 0))
        .where(LLMUsage.ad_test_id.in_(test_ids))
        .group_by(LLMUsage.ad_test_id)
    )
    return {tid: float(c) for tid, c in res.all()}


async def list_tests(
    db: AsyncSession, cursor: str | None, limit: int, status: str | None, user_email: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    stmt = (
        select(AdTest, User.email)
        .join(User, User.id == AdTest.user_id)
        .order_by(AdTest.created_at.desc(), AdTest.id.desc())
        .limit(limit + 1)
    )
    if status:
        stmt = stmt.where(AdTest.status == status)
    if user_email:
        stmt = stmt.where(User.email.ilike(f"%{user_email}%"))
    cur = decode_cursor(cursor)
    if cur:
        t, rid = cur
        stmt = stmt.where((AdTest.created_at < t) | ((AdTest.created_at == t) & (AdTest.id < rid)))
    rows = list((await db.execute(stmt)).all())
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1][0].created_at, rows[-1][0].id)
    costs = await _cost_by_test(db, [t.id for t, _ in rows])
    return [test_item(t, email, costs.get(t.id, 0.0)) for t, email in rows], next_cursor


def test_item(t: AdTest, email: str | None, cost: float) -> dict[str, Any]:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_email": email,
        "title": t.title,
        "status": t.status,
        "tier_code": t.tier_code,
        "country_code": t.country_code,
        "post_type": t.post_type,
        "goal": t.goal,
        "platforms": [p["code"] for p in (t.platforms or [])],
        "progress_pct": t.progress_pct,
        "stage": t.stage,
        "score": t.score,
        "paid_via": t.paid_via,
        "cost_usd": round(cost, 4),
        "created_at": t.created_at,
        "finished_at": t.finished_at,
    }


async def test_detail(db: AsyncSession, test_id: uuid.UUID) -> dict[str, Any]:
    test = await db.get(AdTest, test_id)
    if test is None:
        raise ApiError(ErrorCode.not_found, "Test not found")
    user = await db.get(User, test.user_id)
    usage_rows = (await db.execute(select(LLMUsage).where(LLMUsage.ad_test_id == test.id))).scalars().all()
    by_stage: dict[str, dict[str, float]] = {}
    tokens = {"input": 0, "cached": 0, "output": 0}
    total_cost = 0.0
    for u in usage_rows:
        s = by_stage.setdefault(
            u.stage,
            {
                "calls": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model": u.model,
            },
        )
        s["calls"] += 1
        s["input_tokens"] += u.input_tokens
        s["cached_tokens"] += u.cached_tokens
        s["output_tokens"] += u.output_tokens
        s["cost_usd"] = round(s["cost_usd"] + float(u.cost_usd), 6)
        tokens["input"] += u.input_tokens
        tokens["cached"] += u.cached_tokens
        tokens["output"] += u.output_tokens
        total_cost += float(u.cost_usd)
    state = test.pipeline_state or {}
    stages_out = []
    for st in STAGES:
        info = (state.get("stages") or {}).get(st) or {}
        stages_out.append(
            {
                "stage": st,
                "status": info.get("status", "pending"),
                "started_at": info.get("started_at"),
                "finished_at": info.get("finished_at"),
                "detail": info.get("detail"),
            }
        )
    errors = []
    if test.error:
        errors.append(test.error)
    payment = None
    if test.payment_id:
        p = await db.get(Payment, test.payment_id)
        if p:
            payment = {
                "id": str(p.id),
                "method": p.method,
                "mode": p.mode,
                "status": p.status,
                "amount_usd_minor": p.amount_usd_minor,
                "payment_code": p.payment_code,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
    audit_rows = await audit.entries_for(db, "ad_test", test.id, limit=30)
    base = test_item(test, user.email if user else None, total_cost)
    base.update(
        {
            "stages": stages_out,
            "cost_breakdown": [{"stage": k, **v} for k, v in by_stage.items()],
            "llm_calls": len(usage_rows),
            "tokens": tokens,
            "errors": errors,
            "settings_versions": test.settings_versions or {},
            "payment": payment,
            "cancel_count": test.cancel_count,
            "audit": [
                {
                    "action": a.action,
                    "actor_id": str(a.actor_id) if a.actor_id else None,
                    "data": a.data,
                    "created_at": a.created_at.isoformat(),
                }
                for a in audit_rows
            ],
            "stage_label": STAGE_LABELS.get(test.stage or "", None),
        }
    )
    return base


async def rerun_test(db: AsyncSession, admin: User, test_id: uuid.UUID, ip: str | None) -> AdTest:
    test = await test_state.lock_test(db, test_id)
    if test.status not in ("failed", "completed"):
        raise ApiError(
            ErrorCode.invalid_state, f"Only failed or completed tests can be re-run (status: {test.status})"
        )
    from app.services.cancel import cancel_key

    await get_redis().delete(cancel_key(test.id))
    test.rerun_available = False
    test.pipeline_state = {k: v for k, v in (test.pipeline_state or {}).items() if k == "frozen_inputs"}
    test_state.transition(test, "queued")
    await audit.log(
        db, actor_id=admin.id, action="admin.test.rerun", entity="ad_test", entity_id=test.id, data={}, ip=ip
    )
    await db.flush()
    await queue.enqueue_run(test.id)
    return test


# --------------------------------------------------------------------------- users


async def list_users(
    db: AsyncSession, cursor: str | None, limit: int, q: str | None
) -> tuple[list[dict[str, Any]], str | None]:
    stmt = select(User).order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)
    if q:
        stmt = stmt.where((User.email.ilike(f"%{q}%")) | (User.name.ilike(f"%{q}%")))
    cur = decode_cursor(cursor)
    if cur:
        t, rid = cur
        stmt = stmt.where((User.created_at < t) | ((User.created_at == t) & (User.id < rid)))
    rows = list((await db.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)
    return [await user_item(db, u) for u in rows], next_cursor


async def user_item(db: AsyncSession, u: User) -> dict[str, Any]:
    tests_count = int(
        (
            await db.execute(select(func.count()).select_from(AdTest).where(AdTest.user_id == u.id))
        ).scalar_one()
    )
    used = (
        int(
            (
                await db.execute(
                    select(func.count()).select_from(TrialGrant).where(TrialGrant.user_id == u.id)
                )
            ).scalar_one()
        )
        > 0
    )
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "role": u.role,
        "email_verified": u.email_verified_at is not None,
        "country": u.country,
        "is_blocked": u.is_blocked,
        "trial_used": used,
        "tests_count": tests_count,
        "created_at": u.created_at,
        "deleted_at": u.deleted_at,
    }


async def patch_user(
    db: AsyncSession,
    admin: User,
    user_id: uuid.UUID,
    *,
    is_blocked: bool | None,
    reset_trial: bool | None,
    role: str | None,
    ip: str | None,
) -> dict[str, Any]:
    user = await db.get(User, user_id)
    if user is None:
        raise ApiError(ErrorCode.not_found, "User not found")
    changes: dict[str, Any] = {}
    if is_blocked is not None and is_blocked != user.is_blocked:
        user.is_blocked = is_blocked
        changes["is_blocked"] = is_blocked
    if reset_trial:
        n = await trial.reset_for_user(db, user.id)
        changes["trial_reset"] = n
    if role is not None and role != user.role:
        if user.id == admin.id and role != "admin":
            raise ApiError(ErrorCode.validation_error, "You cannot remove your own admin role")
        user.role = role
        changes["role"] = role
    await audit.log(
        db,
        actor_id=admin.id,
        action="admin.user.patch",
        entity="user",
        entity_id=user.id,
        data=changes,
        ip=ip,
    )
    await db.flush()
    return await user_item(db, user)


# --------------------------------------------------------------------------- prices


async def get_prices(db: AsyncSession) -> dict[str, Any]:
    rows = (
        (await db.execute(select(Price).where(Price.currency == "USD").order_by(Price.tier_code)))
        .scalars()
        .all()
    )
    return {
        "currency": "USD",
        "items": [
            {
                "tier_code": p.tier_code,
                "currency": p.currency,
                "amount_minor": p.amount_minor,
                "extra_platform_minor": p.extra_platform_minor,
                "active": p.active,
            }
            for p in rows
        ],
    }


async def put_prices(
    db: AsyncSession, admin: User, items: list[dict[str, Any]], change_note: str, ip: str | None
) -> dict[str, Any]:
    for item in items:
        row = (
            await db.execute(
                select(Price).where(Price.tier_code == item["tier_code"], Price.currency == "USD")
            )
        ).scalar_one_or_none()
        if row is None:
            row = Price(
                tier_code=item["tier_code"],
                currency="USD",
                amount_minor=int(item["amount_minor"]),
                extra_platform_minor=int(item.get("extra_platform_minor") or 0),
                method="any",
                active=bool(item.get("active", True)),
            )
            db.add(row)
        else:
            row.amount_minor = int(item["amount_minor"])
            if item.get("extra_platform_minor") is not None:
                row.extra_platform_minor = int(item["extra_platform_minor"])
            row.active = bool(item.get("active", True))
    # keep the extra_platform row's amount in sync with per-tier extra values for display
    extra = (
        await db.execute(select(Price).where(Price.tier_code == "extra_platform", Price.currency == "USD"))
    ).scalar_one_or_none()
    if extra is not None:
        for row in (
            (
                await db.execute(
                    select(Price).where(Price.currency == "USD", Price.tier_code != "extra_platform")
                )
            )
            .scalars()
            .all()
        ):
            row.extra_platform_minor = extra.amount_minor
    await audit.log(
        db,
        actor_id=admin.id,
        action="admin.prices.update",
        entity="prices",
        entity_id="USD",
        data={"items": items, "change_note": change_note},
        ip=ip,
    )
    await db.flush()
    return await get_prices(db)


# --------------------------------------------------------------------------- metrics


async def metrics(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    s = get_settings()
    since = now_utc() - timedelta(days=days)
    rev_rows = (
        await db.execute(
            select(Payment.method, func.coalesce(func.sum(Payment.amount_usd_minor), 0))
            .where(Payment.status == "succeeded", Payment.paid_at >= since)
            .group_by(Payment.method)
        )
    ).all()
    revenue_by_method = {m: int(v) for m, v in rev_rows}
    revenue_total = sum(revenue_by_method.values())
    ai_cost = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(LLMUsage.created_at >= since)
            )
        ).scalar_one()
        or 0
    )
    day_col = func.date_trunc(literal("day"), AdTest.created_at).label("day")
    per_day_rows = (
        await db.execute(
            select(day_col, func.count())
            .where(AdTest.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
    ).all()
    tests_per_day = [{"day": d.date().isoformat(), "count": int(c)} for d, c in per_day_rows]
    approval_rows = (
        await db.execute(
            select(Payment.created_at, Payment.approved_at).where(
                Payment.method == "manual",
                Payment.status == "succeeded",
                Payment.approved_at.is_not(None),
                Payment.created_at >= since,
            )
        )
    ).all()
    avg_approval = None
    if approval_rows:
        avg_approval = round(
            sum((b - a).total_seconds() for a, b in approval_rows) / len(approval_rows) / 60.0, 1
        )
    failed = int(
        (
            await db.execute(
                select(func.count())
                .select_from(AdTest)
                .where(AdTest.status == "failed", AdTest.created_at >= since)
            )
        ).scalar_one()
    )
    completed = int(
        (
            await db.execute(
                select(func.count())
                .select_from(AdTest)
                .where(AdTest.status == "completed", AdTest.created_at >= since)
            )
        ).scalar_one()
    )
    pending_manual = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.method == "manual", Payment.status == "pending_review")
            )
        ).scalar_one()
    )
    start_today = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    today_spend = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                    LLMUsage.created_at >= start_today
                )
            )
        ).scalar_one()
        or 0
    )
    revenue_usd = revenue_total / 100.0
    margin = revenue_usd - ai_cost
    return {
        "revenue_by_method": revenue_by_method,
        "revenue_total_usd_minor": revenue_total,
        "ai_cost_usd": round(ai_cost, 4),
        "gross_margin_usd": round(margin, 2),
        "gross_margin_pct": round(100.0 * margin / revenue_usd, 1) if revenue_usd > 0 else None,
        "tests_per_day": tests_per_day,
        "average_approval_time_min": avg_approval,
        "failed_tests": failed,
        "completed_tests": completed,
        "pending_manual_orders": pending_manual,
        "llm_spend_today_usd": round(today_spend, 4),
        "llm_daily_cap_usd": s.DAILY_LLM_SPEND_CAP_USD,
    }
