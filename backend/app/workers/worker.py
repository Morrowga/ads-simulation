"""Arq worker settings and cron jobs (stuck tests, expired drafts, expired manual orders, daily LLM spend)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from arq import cron
from sqlalchemy import func, select

from app.config import get_settings
from app.db import dispose_engine, session_scope
from app.logging_setup import configure_logging
from app.models import AdTest, LLMUsage, User
from app.security import now_utc
from app.services import audit, email_service, queue, settings_service
from app.services.payments import manual
from app.services.queue import redis_settings
from app.services.redis_client import close_redis
from app.workers.run_test import run_test

log = logging.getLogger("advar.worker")


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    log.info(
        "worker started env=%s llm=%s payments=%s",
        get_settings().APP_ENV,
        get_settings().LLM_PROVIDER,
        get_settings().PAYMENT_MODE,
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await queue.close_pool()
    await close_redis()
    await dispose_engine()


async def recover_stuck_tests(ctx: dict[str, Any]) -> dict[str, Any]:
    """Tests running for more than STUCK_RUNNING_MINUTES without a heartbeat: requeue once, then fail with a free re-run."""
    s = get_settings()
    cutoff = now_utc() - timedelta(minutes=s.STUCK_RUNNING_MINUTES)
    requeued, failed = 0, 0
    async with session_scope() as db:
        res = await db.execute(
            select(AdTest)
            .where(
                AdTest.status == "running",
                (AdTest.heartbeat_at < cutoff)
                | (AdTest.heartbeat_at.is_(None) & (AdTest.started_at < cutoff)),
            )
            .with_for_update(skip_locked=True)
        )
        for test in res.scalars().all():
            state = dict(test.pipeline_state or {})
            attempts = int(state.get("recovery_attempts", 0))
            if attempts < 1:
                state["recovery_attempts"] = attempts + 1
                test.pipeline_state = state
                test.status = "queued"
                test.queued_at = now_utc()
                await db.flush()
                await queue.enqueue_run(test.id)
                requeued += 1
                await audit.log(
                    db,
                    actor_id=None,
                    action="test.recover_requeue",
                    entity="ad_test",
                    entity_id=test.id,
                    data={"attempt": attempts + 1},
                )
            else:
                test.status = "failed"
                test.finished_at = now_utc()
                test.rerun_available = True
                test.cancel_window_open = False
                test.error = {
                    "code": "stuck",
                    "message": f"No progress for more than {s.STUCK_RUNNING_MINUTES} minutes",
                    "stage": test.stage,
                }
                failed += 1
                await audit.log(
                    db,
                    actor_id=None,
                    action="test.recover_failed",
                    entity="ad_test",
                    entity_id=test.id,
                    data={"stage": test.stage},
                )
                user = await db.get(User, test.user_id)
                if user:
                    await email_service.send_test_failed(user.email, test.title, str(test.id))
    if requeued or failed:
        log.info("recover_stuck_tests requeued=%s failed=%s", requeued, failed)
    return {"requeued": requeued, "failed": failed}


async def expire_unpaid_drafts(ctx: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    cutoff = now_utc() - timedelta(days=s.DRAFT_EXPIRY_DAYS)
    closed = 0
    async with session_scope() as db:
        res = await db.execute(
            select(AdTest)
            .where(
                AdTest.status.in_(["draft", "awaiting_payment"]),
                AdTest.payment_id.is_(None),
                AdTest.updated_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
        for test in res.scalars().all():
            test.status = "failed"
            test.finished_at = now_utc()
            test.error = {
                "code": "expired",
                "message": f"Unpaid draft expired after {s.DRAFT_EXPIRY_DAYS} days",
            }
            closed += 1
            await audit.log(
                db, actor_id=None, action="test.expire_draft", entity="ad_test", entity_id=test.id, data={}
            )
    return {"closed": closed}


async def expire_manual_orders(ctx: dict[str, Any]) -> dict[str, Any]:
    async with session_scope() as db:
        n = await manual.expire_due(db)
    if n:
        log.info("expired %s manual orders", n)
    return {"expired": n}


async def daily_llm_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    """Sum yesterday's and today's spend, store it in settings and alert admins near the cap."""
    s = get_settings()
    now = now_utc()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_scope() as db:
        today = float(
            (
                await db.execute(
                    select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                        LLMUsage.created_at >= start_today
                    )
                )
            ).scalar_one()
            or 0
        )
        yesterday = float(
            (
                await db.execute(
                    select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                        LLMUsage.created_at >= start_today - timedelta(days=1),
                        LLMUsage.created_at < start_today,
                    )
                )
            ).scalar_one()
            or 0
        )
        await settings_service.set_many(
            db,
            {
                "llm_spend_summary": {
                    "today_usd": round(today, 4),
                    "yesterday_usd": round(yesterday, 4),
                    "cap_usd": s.DAILY_LLM_SPEND_CAP_USD,
                    "updated_at": now.isoformat(),
                    "cap_reached": today >= s.DAILY_LLM_SPEND_CAP_USD,
                }
            },
        )
        if today >= 0.8 * s.DAILY_LLM_SPEND_CAP_USD:
            res = await db.execute(select(User.email).where(User.role == "admin", User.deleted_at.is_(None)))
            for (email,) in res.all():
                await email_service.send_admin_notice(
                    email,
                    "LLM spend near the daily cap",
                    f"Spend today: ${today:.2f} of ${s.DAILY_LLM_SPEND_CAP_USD:.2f}. New tests pause when the cap is reached.",
                )
    return {"today_usd": today, "yesterday_usd": yesterday}


class WorkerSettings:
    functions = [run_test]
    cron_jobs = [
        cron(recover_stuck_tests, minute={0, 10, 20, 30, 40, 50}, run_at_startup=True, unique=True),
        cron(expire_manual_orders, minute={5, 35}, unique=True),
        cron(expire_unpaid_drafts, hour={3}, minute={15}, unique=True),
        cron(daily_llm_summary, minute={0}, unique=True),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings()
    job_timeout = get_settings().JOB_TIMEOUT_SEC
    max_tries = 2
    max_jobs = 2
    keep_result = 3600
    retry_jobs = True
    health_check_interval = 60
