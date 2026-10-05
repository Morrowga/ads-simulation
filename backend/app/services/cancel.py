"""Cancel inside the cancel window and restart of prepaid drafts / failed tests (Backend document 6.6)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, User
from app.security import now_utc
from app.services import audit, queue, rate_limit, test_state, tests_service
from app.services import fingerprint as fp
from app.services.redis_client import get_redis


def cancel_key(test_id: uuid.UUID | str) -> str:
    return f"cancel:{test_id}"


async def cancel(db: AsyncSession, user: User, test_id: uuid.UUID, ip: str | None = None) -> dict[str, Any]:
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    if test.status == "queued":
        # nothing has started: back to a prepaid draft, payment kept, free restart
        test.cancel_count += 1
        test.free_restart_available = test.cancel_count == 1
        test.cancelled_at = now_utc()
        test_state.transition(test, "draft")
        if not test.free_restart_available:
            await _consume_payment(db, test)
        await get_redis().set(cancel_key(test.id), "1", ex=3600)
        await audit.log(
            db,
            actor_id=user.id,
            action="test.cancel",
            entity="ad_test",
            entity_id=test.id,
            data={"from": "queued", "cancel_count": test.cancel_count},
            ip=ip,
        )
        await db.flush()
        return _out(test, "Test cancelled before it started; you can restart it for free after editing")
    test_state.ensure_status(test, "running")
    if not test.cancel_window_open:
        raise ApiError(
            ErrorCode.cancel_window_closed,
            "The cancel window has closed: the simulation already started",
            details={"stage": test.stage},
        )
    test.cancel_count += 1
    test.free_restart_available = test.cancel_count == 1
    test.cancelled_at = now_utc()
    test_state.transition(test, "draft")
    if not test.free_restart_available:
        await _consume_payment(db, test)
    await get_redis().set(cancel_key(test.id), "1", ex=3600)
    await audit.log(
        db,
        actor_id=user.id,
        action="test.cancel",
        entity="ad_test",
        entity_id=test.id,
        data={"from": "running", "stage": test.stage, "cancel_count": test.cancel_count},
        ip=ip,
    )
    await db.flush()
    msg = (
        "Test cancelled; the payment is kept and one free restart is available"
        if test.free_restart_available
        else "Test cancelled; a new payment is needed to run it again"
    )
    return _out(test, msg)


async def _consume_payment(db: AsyncSession, test: AdTest) -> None:
    """Second cancel: the payment is used up (status `consumed`), the test needs a new payment."""
    from app.models import Payment

    if test.payment_id is not None:
        payment = await db.get(Payment, test.payment_id)
        if payment is not None and payment.status == "succeeded":
            payment.status = "consumed"
            payment.cancel_reason = "used by a run that was cancelled twice"
    test.payment_id = None
    test.paid_via = None


def _out(test: AdTest, message: str) -> dict[str, Any]:
    return {
        "status": test.status,
        "cancel_count": test.cancel_count,
        "free_restart_available": test.free_restart_available,
        "message": message,
    }


async def restart(db: AsyncSession, user: User, test_id: uuid.UUID, ip: str | None = None) -> AdTest:
    """draft (prepaid, free restart) -> queued, or failed (free re-run) -> queued. Fingerprint re-checked."""
    await rate_limit.enforce(rate_limit.TEST_START, str(user.id))
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    if test.status == "failed":
        if not test.rerun_available:
            raise ApiError(ErrorCode.restart_not_available, "No free re-run available for this test")
        test.rerun_available = False
        test.cancel_count = 0
        await get_redis().delete(cancel_key(test.id))
        test_state.transition(test, "queued")
        await audit.log(
            db,
            actor_id=user.id,
            action="test.rerun",
            entity="ad_test",
            entity_id=test.id,
            data={"reason": "failed"},
            ip=ip,
        )
        await db.flush()
        await queue.enqueue_run(test.id)
        return test
    test_state.ensure_status(test, "draft", "awaiting_payment")
    if not test_state.is_prepaid(test):
        raise ApiError(
            ErrorCode.payment_required,
            "This test is not paid; confirm and pay to run it",
            details={"status": test.status},
        )
    if not test.free_restart_available:
        raise ApiError(
            ErrorCode.restart_not_available,
            "No free restart left: a new payment is needed",
            details={"cancel_count": test.cancel_count},
        )
    # re-check inputs and the fingerprint against completed tests
    assets = await tests_service.assets_for(db, test.id)
    if not assets or not test.platforms or not test.profile_snapshot:
        raise ApiError(
            ErrorCode.validation_error,
            "The test is not complete: media, platforms and a profile are required",
        )
    digest, payload = fp.fingerprint(test, assets, get_settings().ENGINE_VERSION)
    from sqlalchemy import select

    dup = (
        (
            await db.execute(
                select(AdTest).where(
                    AdTest.user_id == user.id,
                    AdTest.status == "completed",
                    AdTest.fingerprint == digest,
                    AdTest.id != test.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if dup is not None:
        raise ApiError(
            ErrorCode.duplicate_test,
            "An identical completed test already exists",
            details={"test_id": str(dup.id), "title": dup.title},
        )
    test.fingerprint = digest
    test.fingerprint_payload = payload
    test.engine_version = get_settings().ENGINE_VERSION
    test.free_restart_available = False
    if test.status == "awaiting_payment":
        test_state.transition(test, "draft")
    await get_redis().delete(cancel_key(test.id))
    test_state.transition(test, "queued")
    await audit.log(
        db,
        actor_id=user.id,
        action="test.restart",
        entity="ad_test",
        entity_id=test.id,
        data={"prepaid": True, "cancel_count": test.cancel_count},
        ip=ip,
    )
    await db.flush()
    await queue.enqueue_run(test.id)
    return test
