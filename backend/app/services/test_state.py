"""The ad-test state machine. Every status change goes through `transition` on a row locked with
SELECT ... FOR UPDATE, so a duplicated webhook and an admin click can never enqueue a test twice."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ApiError, ErrorCode
from app.models import AdTest
from app.security import now_utc

# (from, to): trigger
ALLOWED: dict[tuple[str, str], str] = {
    ("draft", "awaiting_payment"): "confirm passed",
    ("awaiting_payment", "draft"): "user edits the test again",
    ("awaiting_payment", "queued"): "trial used / card payment confirmed",
    ("awaiting_payment", "payment_review"): "manual order created",
    ("payment_review", "queued"): "admin approved the order",
    ("payment_review", "awaiting_payment"): "order cancelled or expired",
    ("queued", "running"): "worker picked the job",
    ("queued", "draft"): "user cancelled before the worker started",
    ("queued", "failed"): "job could not start",
    ("running", "draft"): "user cancelled inside the window",
    ("draft", "queued"): "prepaid restart",
    ("running", "completed"): "report saved",
    ("running", "failed"): "unrecoverable error",
    ("running", "queued"): "stuck run requeued",
    ("failed", "queued"): "free re-run",
    ("completed", "queued"): "admin re-run",
    ("completed", "refunded"): "refund",
    ("failed", "refunded"): "refund",
    ("draft", "failed"): "expired unpaid draft closed",
}

EDITABLE = ("draft", "awaiting_payment")
CANCEL_WINDOW_STAGES = ("prepare", "analyze_ad", "population", "archetypes", "react")


async def lock_test(db: AsyncSession, test_id: uuid.UUID) -> AdTest:
    res = await db.execute(select(AdTest).where(AdTest.id == test_id).with_for_update())
    test = res.scalar_one_or_none()
    if test is None:
        raise ApiError(ErrorCode.not_found, "Test not found")
    return test


def ensure_status(test: AdTest, *allowed: str) -> None:
    if test.status not in allowed:
        raise ApiError(
            ErrorCode.invalid_state,
            f"Test is {test.status}; expected {' or '.join(allowed)}",
            details={"status": test.status, "expected": list(allowed)},
        )


def can_transition(from_status: str, to_status: str) -> bool:
    return (from_status, to_status) in ALLOWED


def transition(test: AdTest, to_status: str, **fields: Any) -> AdTest:
    """Apply a transition in memory (the caller holds the row lock and commits)."""
    key = (test.status, to_status)
    if key not in ALLOWED:
        raise ApiError(
            ErrorCode.invalid_state,
            f"Cannot move test from {test.status} to {to_status}",
            details={"from": test.status, "to": to_status},
        )
    now = now_utc()
    test.status = to_status
    if to_status == "queued":
        test.queued_at = now
        test.progress_pct = 0
        test.stage = None
        test.error = None
        test.finished_at = None
        test.cancel_window_open = True
    elif to_status == "running":
        test.started_at = now
        test.heartbeat_at = now
    elif to_status in ("completed", "failed"):
        test.finished_at = now
        test.cancel_window_open = False
    elif to_status == "draft":
        test.cancel_window_open = False
    for k, v in fields.items():
        setattr(test, k, v)
    return test


def is_prepaid(test: AdTest) -> bool:
    return test.payment_id is not None and test.paid_via is not None


def to_summary(test: AdTest) -> dict[str, Any]:
    return {"id": str(test.id), "status": test.status, "stage": test.stage, "progress_pct": test.progress_pct}
