"""Myanmar manual orders: payment code, MMK amount fixed from the current rate, admin approve/cancel, expiry."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, Country, Payment, User
from app.security import now_utc, payment_code
from app.services import audit, email_service, fx, pricing, queue, settings_service, test_state


async def country_allows_manual(db: AsyncSession, country_code: str) -> bool:
    country = await db.get(Country, country_code)
    return country is not None and "manual" in (country.payment_methods or [])


async def unique_payment_code(db: AsyncSession) -> str:
    for _ in range(20):
        code = payment_code()
        res = await db.execute(select(Payment.id).where(Payment.payment_code == code))
        if res.first() is None:
            return code
    raise ApiError(ErrorCode.internal_error, "Could not allocate a payment code")


async def create_order(
    db: AsyncSession, user: User, test: AdTest, ip: str | None = None
) -> tuple[Payment, dict[str, Any]]:
    """test must be locked and in awaiting_payment."""
    s = get_settings()
    if not await country_allows_manual(db, test.country_code):
        raise ApiError(
            ErrorCode.method_not_allowed,
            "Manual payment is only available in countries with the manual method",
            details={"country": test.country_code},
        )
    test_state.ensure_status(test, "awaiting_payment")
    country = await db.get(Country, test.country_code)
    rate = await fx.get_rate(db, country.currency)
    if rate is None:
        raise ApiError(
            ErrorCode.internal_error, f"No exchange rate for {country.currency}; ask the admin to set one"
        )
    price = await pricing.price_for(db, test.tier_code, len(test.platforms))
    local_minor = fx.convert_usd_minor(
        price["total_usd_minor"], rate.rate_per_usd, country.currency, friendly=True
    )
    manual_settings = await settings_service.get(db, "manual_payment", {})
    expiry_hours = int(manual_settings.get("expiry_hours") or s.MANUAL_ORDER_EXPIRY_HOURS)
    # cancel any previous open manual order for this test
    res = await db.execute(
        select(Payment).where(
            Payment.ad_test_id == test.id, Payment.method == "manual", Payment.status == "pending_review"
        )
    )
    for old in res.scalars().all():
        old.status = "cancelled"
        old.cancel_reason = "replaced by a new order"
    payment = Payment(
        user_id=user.id,
        ad_test_id=test.id,
        method="manual",
        mode="manual",
        status="pending_review",
        amount_usd_minor=price["total_usd_minor"],
        currency="USD",
        local_currency=country.currency,
        local_amount_minor=local_minor,
        fx_rate=rate.rate_per_usd,
        payment_code=await unique_payment_code(db),
        expires_at=now_utc() + timedelta(hours=expiry_hours),
        tier_code=test.tier_code,
        platform_count=len(test.platforms),
    )
    db.add(payment)
    await db.flush()
    test_state.transition(test, "payment_review")
    await audit.log(
        db,
        actor_id=user.id,
        action="payment.manual.create",
        entity="payment",
        entity_id=payment.id,
        data={
            "test_id": str(test.id),
            "payment_code": payment.payment_code,
            "local_amount_minor": local_minor,
            "local_currency": country.currency,
        },
        ip=ip,
    )
    await db.flush()
    info = {
        "accounts": manual_settings.get("accounts", []),
        "instructions": manual_settings.get("instructions", ""),
        "social_links": await settings_service.get(db, "social_links", {}),
        "expires_at": payment.expires_at,
        "expiry_hours": expiry_hours,
        "local_display": fx.format_money(local_minor, country.currency),
        "usd_display": fx.format_money(price["total_usd_minor"], "USD"),
    }
    await email_service.send_manual_order(
        user.email, test.title, payment.payment_code, info["local_display"], expiry_hours
    )
    return payment, info


async def approve(
    db: AsyncSession, admin: User, payment_id: uuid.UUID, admin_reference: str | None, ip: str | None = None
) -> Payment:
    payment = await _lock_payment(db, payment_id)
    if payment.method != "manual":
        raise ApiError(ErrorCode.payment_invalid_state, "Only manual orders can be approved")
    if payment.status == "succeeded":
        return payment
    if payment.status != "pending_review":
        raise ApiError(
            ErrorCode.payment_invalid_state,
            f"Order is {payment.status}, not pending review",
            details={"status": payment.status},
        )
    test = await test_state.lock_test(db, payment.ad_test_id)
    payment.status = "succeeded"
    payment.paid_at = now_utc()
    payment.approved_by = admin.id
    payment.approved_at = now_utc()
    payment.admin_reference = admin_reference
    test.paid_via = "manual"
    test.payment_id = payment.id
    test_state.transition(test, "queued")
    await audit.log(
        db,
        actor_id=admin.id,
        action="payment.manual.approve",
        entity="payment",
        entity_id=payment.id,
        data={
            "payment_code": payment.payment_code,
            "admin_reference": admin_reference,
            "test_id": str(test.id),
        },
        ip=ip,
    )
    await db.flush()
    await queue.enqueue_run(test.id)
    user = await db.get(User, payment.user_id)
    if user:
        await email_service.send_manual_approved(user.email, test.title, payment.payment_code or "")
    return payment


async def cancel(
    db: AsyncSession,
    admin: User | None,
    payment_id: uuid.UUID,
    reason: str,
    ip: str | None = None,
    expired: bool = False,
) -> Payment:
    payment = await _lock_payment(db, payment_id)
    if payment.method != "manual":
        raise ApiError(ErrorCode.payment_invalid_state, "Only manual orders can be cancelled")
    if payment.status != "pending_review":
        raise ApiError(
            ErrorCode.payment_invalid_state,
            f"Order is {payment.status}, not pending review",
            details={"status": payment.status},
        )
    test = await test_state.lock_test(db, payment.ad_test_id)
    payment.status = "expired" if expired else "cancelled"
    payment.cancel_reason = reason
    if test.status == "payment_review":
        test_state.transition(test, "awaiting_payment")
    await audit.log(
        db,
        actor_id=admin.id if admin else None,
        action="payment.manual.expire" if expired else "payment.manual.cancel",
        entity="payment",
        entity_id=payment.id,
        data={"payment_code": payment.payment_code, "reason": reason, "test_id": str(test.id)},
        ip=ip,
    )
    await db.flush()
    user = await db.get(User, payment.user_id)
    if user:
        await email_service.send_manual_cancelled(user.email, test.title, payment.payment_code or "", reason)
    return payment


async def expire_due(db: AsyncSession) -> int:
    res = await db.execute(
        select(Payment.id).where(
            Payment.method == "manual", Payment.status == "pending_review", Payment.expires_at < now_utc()
        )
    )
    ids = [pid for (pid,) in res.all()]
    for pid in ids:
        await cancel(
            db,
            None,
            pid,
            f"Order expired after {get_settings().MANUAL_ORDER_EXPIRY_HOURS} hours without payment",
            expired=True,
        )
    return len(ids)


async def _lock_payment(db: AsyncSession, payment_id: uuid.UUID) -> Payment:
    res = await db.execute(select(Payment).where(Payment.id == payment_id).with_for_update())
    payment = res.scalar_one_or_none()
    if payment is None:
        raise ApiError(ErrorCode.payment_not_found, "Payment not found")
    return payment


async def auto_approve_if_mock(db: AsyncSession, payment: Payment) -> bool:
    s = get_settings()
    if s.PAYMENT_MODE == "mock" and s.MANUAL_AUTO_APPROVE_IN_MOCK:
        res = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = res.scalar_one_or_none()
        if admin is None:
            return False
        await approve(db, admin, payment.id, "auto-approved (mock mode)")
        return True
    return False
