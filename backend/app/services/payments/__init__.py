"""Payment orchestration: checkout info, trial, card (mock/Stripe), webhook handling, refunds."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, Country, Payment, StripeEvent, User
from app.security import now_utc
from app.services import (
    audit,
    email_service,
    fx,
    pricing,
    queue,
    rate_limit,
    test_state,
    tests_service,
    trial,
)
from app.services.confirm import assert_not_duplicate
from app.services.payments import manual
from app.services.payments.base import CardGateway
from app.services.payments.mock_gateway import MockGateway
from app.services.payments.stripe_gateway import StripeGateway


def get_gateway() -> CardGateway:
    mode = get_settings().PAYMENT_MODE
    if mode == "mock":
        return MockGateway()
    return StripeGateway(mode)


async def checkout_info(db: AsyncSession, user: User, test_id: uuid.UUID) -> dict[str, Any]:
    s = get_settings()
    test = await tests_service.get_owned(db, user, test_id)
    if test.status not in ("awaiting_payment", "payment_review") or not test.fingerprint:
        raise ApiError(
            ErrorCode.confirm_required, "Confirm the test before checkout", details={"status": test.status}
        )
    await assert_not_duplicate(db, user, test)
    country = await db.get(Country, test.country_code)
    methods = list(country.payment_methods or []) if country else ["card"]
    eligible, reason = await trial.eligibility(db, user, test.tier_code)
    if eligible:
        methods.append("trial")
    tiers = await pricing.tiers_with_prices(db, country.currency if country else None, len(test.platforms))
    selected = next((t for t in tiers if t["code"] == test.tier_code), None)
    if selected is None:
        raise ApiError(ErrorCode.validation_error, "Selected tier has no price")
    local = await fx.local_amount(db, selected["total_usd_minor"], country.currency) if country else None
    return {
        "test_id": test.id,
        "status": test.status,
        "country_code": test.country_code,
        "currency": country.currency if country else "USD",
        "platforms": [p["code"] for p in test.platforms],
        "tiers": [
            {
                "code": t["code"],
                "name": t["name"],
                "selected": t["code"] == test.tier_code,
                "tier_usd_minor": t["price_usd_minor"],
                "extra_platforms": t["extra_platforms"],
                "extra_platform_usd_minor": t["extra_platform_usd_minor"],
                "total_usd_minor": t["total_usd_minor"],
                "display": fx.format_money(t["total_usd_minor"], "USD"),
                "local": await fx.local_amount(db, t["total_usd_minor"], country.currency)
                if country
                else None,
            }
            for t in tiers
        ],
        "selected_tier": test.tier_code,
        "total_usd_minor": selected["total_usd_minor"],
        "total_display": fx.format_money(selected["total_usd_minor"], "USD"),
        "local": local,
        "trial_available": eligible,
        "trial_reason": reason,
        "methods": methods,
        "payment_mode": s.PAYMENT_MODE,
        "test_mode_banner": s.PAYMENT_MODE != "stripe_live",
    }


async def pay_with_trial(
    db: AsyncSession, user: User, test_id: uuid.UUID, ip: str | None, device_hash: str | None
) -> tuple[Payment, AdTest]:
    await rate_limit.enforce(rate_limit.TEST_START, str(user.id))
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    test_state.ensure_status(test, "awaiting_payment")
    await assert_not_duplicate(db, user, test)
    if user.email_verified_at is None:
        raise ApiError(ErrorCode.email_not_verified, "Verify your e-mail to use the free trial")
    await trial.grant(db, user, test.id, ip, device_hash)
    payment = Payment(
        user_id=user.id,
        ad_test_id=test.id,
        method="trial",
        mode="trial",
        status="succeeded",
        amount_usd_minor=0,
        currency="USD",
        paid_at=now_utc(),
        tier_code=test.tier_code,
        platform_count=len(test.platforms),
    )
    db.add(payment)
    await db.flush()
    test.paid_via = "trial"
    test.payment_id = payment.id
    test_state.transition(test, "queued")
    await audit.log(
        db,
        actor_id=user.id,
        action="payment.trial",
        entity="payment",
        entity_id=payment.id,
        data={"test_id": str(test.id)},
        ip=ip,
    )
    await db.flush()
    await queue.enqueue_run(test.id)
    return payment, test


async def pay_with_card(
    db: AsyncSession, user: User, test_id: uuid.UUID, ip: str | None
) -> tuple[Payment, AdTest, str | None]:
    s = get_settings()
    await rate_limit.enforce(rate_limit.TEST_START, str(user.id))
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    test_state.ensure_status(test, "awaiting_payment")
    await assert_not_duplicate(db, user, test)
    country = await db.get(Country, test.country_code)
    if country and "card" not in (country.payment_methods or []):
        raise ApiError(
            ErrorCode.method_not_allowed,
            f"Card payments are not offered in {country.name}",
            details={"methods": country.payment_methods},
        )
    price = await pricing.price_for(
        db, test.tier_code, len(test.platforms), country.currency if country else None
    )
    gateway = get_gateway()
    payment = Payment(
        user_id=user.id,
        ad_test_id=test.id,
        method="stripe",
        mode=s.PAYMENT_MODE,
        status="pending",
        amount_usd_minor=price["total_usd_minor"],
        currency="USD",
        local_currency=(price.get("local") or {}).get("currency"),
        local_amount_minor=(price.get("local") or {}).get("amount_minor"),
        fx_rate=(price.get("local") or {}).get("fx_rate"),
        tier_code=test.tier_code,
        platform_count=len(test.platforms),
    )
    db.add(payment)
    await db.flush()
    frontend = s.FRONTEND_URL.rstrip("/")
    result = await gateway.create_checkout(
        user=user,
        test=test,
        payment=payment,
        amount_usd_minor=price["total_usd_minor"],
        success_url=f"{frontend}/tests/{test.id}/checkout?stripe=success",
        cancel_url=f"{frontend}/tests/{test.id}/checkout?stripe=cancel",
    )
    payment.stripe_session_id = result.session_id
    payment.stripe_payment_intent_id = result.payment_intent_id
    payment.checkout_url = result.checkout_url
    if result.status == "succeeded":
        payment.status = "succeeded"
        payment.paid_at = now_utc()
        test.paid_via = "mock"
        test.payment_id = payment.id
        test_state.transition(test, "queued")
        await audit.log(
            db,
            actor_id=user.id,
            action="payment.card.mock",
            entity="payment",
            entity_id=payment.id,
            data={"test_id": str(test.id), "amount_usd_minor": payment.amount_usd_minor},
            ip=ip,
        )
        await db.flush()
        await queue.enqueue_run(test.id)
        await email_service.send_receipt(
            user.email, test.title, fx.format_money(payment.amount_usd_minor, "USD"), "card (test mode)"
        )
    else:
        await audit.log(
            db,
            actor_id=user.id,
            action="payment.card.checkout_created",
            entity="payment",
            entity_id=payment.id,
            data={"test_id": str(test.id), "session_id": result.session_id},
            ip=ip,
        )
        await db.flush()
    return payment, test, result.checkout_url


async def pay_manual(
    db: AsyncSession, user: User, test_id: uuid.UUID, ip: str | None
) -> tuple[Payment, AdTest, dict[str, Any]]:
    await rate_limit.enforce(rate_limit.TEST_START, str(user.id))
    test = await tests_service.get_owned(db, user, test_id, for_update=True)
    await assert_not_duplicate(db, user, test)
    payment, info = await manual.create_order(db, user, test, ip)
    await manual.auto_approve_if_mock(db, payment)
    await db.refresh(test)
    return payment, test, info


# --------------------------------------------------------------------------- Stripe webhook


async def handle_stripe_event(db: AsyncSession, event: dict[str, Any]) -> dict[str, Any]:
    """Idempotent: the event id is stored first; duplicates return without side effects."""
    event_id = str(event.get("id") or "")
    etype = str(event.get("type") or "")
    if not event_id:
        raise ApiError(ErrorCode.validation_error, "Event without id")
    existing = await db.get(StripeEvent, event_id)
    if existing is not None:
        return {"received": True, "event_id": event_id, "duplicate": True, "handled": False}
    db.add(StripeEvent(id=event_id, type=etype, received_at=now_utc(), payload=_jsonable(event)))
    await db.flush()
    obj = (event.get("data") or {}).get("object") or {}
    handled = False
    if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if etype == "checkout.session.async_payment_succeeded" or obj.get("payment_status") == "paid":
            handled = await _mark_paid(db, obj)
    elif etype in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        handled = await _mark_failed(db, obj)
    elif etype == "charge.refunded":
        handled = await _mark_refunded(db, obj)
    elif etype == "charge.dispute.created":
        handled = await _flag_dispute(db, obj)
    row = await db.get(StripeEvent, event_id)
    if row:
        row.processed_at = now_utc()
    await db.flush()
    return {"received": True, "event_id": event_id, "duplicate": False, "handled": handled}


async def _payment_from_object(db: AsyncSession, obj: dict[str, Any]) -> Payment | None:
    meta = obj.get("metadata") or {}
    pid = meta.get("payment_id") or obj.get("client_reference_id")
    payment = None
    if pid:
        try:
            res = await db.execute(select(Payment).where(Payment.id == uuid.UUID(str(pid))).with_for_update())
            payment = res.scalar_one_or_none()
        except ValueError:
            payment = None
    if payment is None and obj.get("id"):
        res = await db.execute(
            select(Payment).where(Payment.stripe_session_id == obj["id"]).with_for_update()
        )
        payment = res.scalar_one_or_none()
    if payment is None and obj.get("payment_intent"):
        pi = (
            obj["payment_intent"]
            if isinstance(obj["payment_intent"], str)
            else obj["payment_intent"].get("id")
        )
        res = await db.execute(
            select(Payment).where(Payment.stripe_payment_intent_id == pi).with_for_update()
        )
        payment = res.scalar_one_or_none()
    return payment


async def _mark_paid(db: AsyncSession, obj: dict[str, Any]) -> bool:
    payment = await _payment_from_object(db, obj)
    if payment is None:
        return False
    if payment.status == "succeeded":
        return True
    test = await test_state.lock_test(db, payment.ad_test_id)
    if obj.get("amount_total") is not None and int(obj["amount_total"]) != int(payment.amount_usd_minor):
        payment.flagged = (
            f"amount mismatch: stripe {obj['amount_total']} vs expected {payment.amount_usd_minor}"
        )
    pi = obj.get("payment_intent")
    payment.stripe_payment_intent_id = (
        pi if isinstance(pi, str) else (pi or {}).get("id") or payment.stripe_payment_intent_id
    )
    payment.stripe_session_id = payment.stripe_session_id or obj.get("id")
    payment.status = "succeeded"
    payment.paid_at = now_utc()
    if test.status == "awaiting_payment":
        test.paid_via = "stripe"
        test.payment_id = payment.id
        test_state.transition(test, "queued")
        await db.flush()
        await queue.enqueue_run(test.id)
    else:
        test.paid_via = test.paid_via or "stripe"
        test.payment_id = test.payment_id or payment.id
    await audit.log(
        db,
        actor_id=None,
        action="payment.card.webhook_paid",
        entity="payment",
        entity_id=payment.id,
        data={"test_id": str(test.id), "session_id": obj.get("id")},
    )
    user = await db.get(User, payment.user_id)
    if user:
        await email_service.send_receipt(
            user.email, test.title, fx.format_money(payment.amount_usd_minor, "USD"), "card"
        )
    return True


async def _mark_failed(db: AsyncSession, obj: dict[str, Any]) -> bool:
    payment = await _payment_from_object(db, obj)
    if payment is None or payment.status == "succeeded":
        return payment is not None
    payment.status = "failed"
    payment.cancel_reason = "checkout expired or payment failed"
    await audit.log(
        db,
        actor_id=None,
        action="payment.card.webhook_failed",
        entity="payment",
        entity_id=payment.id,
        data={"session_id": obj.get("id")},
    )
    return True


async def _mark_refunded(db: AsyncSession, obj: dict[str, Any]) -> bool:
    pi = obj.get("payment_intent")
    pi_id = pi if isinstance(pi, str) else (pi or {}).get("id")
    if not pi_id:
        return False
    res = await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id).with_for_update())
    payment = res.scalar_one_or_none()
    if payment is None:
        return False
    if payment.status == "refunded":
        return True
    payment.status = "refunded"
    payment.refunded_at = now_utc()
    refunds = (obj.get("refunds") or {}).get("data") or [{}]
    payment.refund_ref = payment.refund_ref or (refunds[0].get("id") if refunds else None)
    test = await test_state.lock_test(db, payment.ad_test_id)
    if test.status in ("completed", "failed"):
        test_state.transition(test, "refunded")
    await audit.log(
        db,
        actor_id=None,
        action="payment.card.webhook_refunded",
        entity="payment",
        entity_id=payment.id,
        data={"test_id": str(test.id)},
    )
    return True


async def _flag_dispute(db: AsyncSession, obj: dict[str, Any]) -> bool:
    pi = obj.get("payment_intent")
    pi_id = pi if isinstance(pi, str) else (pi or {}).get("id")
    if not pi_id:
        return False
    res = await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id).with_for_update())
    payment = res.scalar_one_or_none()
    if payment is None:
        return False
    payment.flagged = f"dispute {obj.get('id')}: {obj.get('reason', 'unknown')}"
    await audit.log(
        db,
        actor_id=None,
        action="payment.card.dispute",
        entity="payment",
        entity_id=payment.id,
        data={"dispute": obj.get("id"), "reason": obj.get("reason"), "user_id": str(payment.user_id)},
    )
    return True


# --------------------------------------------------------------------------- admin refund


async def refund(
    db: AsyncSession,
    admin: User,
    payment_id: uuid.UUID,
    reason: str,
    manual_reference: str | None,
    ip: str | None = None,
) -> Payment:
    res = await db.execute(select(Payment).where(Payment.id == payment_id).with_for_update())
    payment = res.scalar_one_or_none()
    if payment is None:
        raise ApiError(ErrorCode.payment_not_found, "Payment not found")
    if payment.method == "trial":
        raise ApiError(ErrorCode.payment_invalid_state, "Trial tests are never refunded")
    if payment.status == "refunded":
        return payment
    if payment.status != "succeeded":
        raise ApiError(
            ErrorCode.payment_invalid_state,
            f"Only succeeded payments can be refunded (status: {payment.status})",
        )
    if payment.method == "manual":
        if not manual_reference:
            raise ApiError(
                ErrorCode.validation_error, "manual_refund_reference is required for manual payments"
            )
        payment.refund_ref = manual_reference
    else:
        result = await get_gateway().refund(payment, reason)
        if not result.ok:
            raise ApiError(ErrorCode.internal_error, result.message, status_code=502)
        payment.refund_ref = result.reference
    payment.status = "refunded"
    payment.refunded_at = now_utc()
    payment.cancel_reason = reason or payment.cancel_reason
    test = await test_state.lock_test(db, payment.ad_test_id)
    if test.status in ("completed", "failed"):
        test_state.transition(test, "refunded")
    await audit.log(
        db,
        actor_id=admin.id,
        action="payment.refund",
        entity="payment",
        entity_id=payment.id,
        data={"test_id": str(test.id), "reason": reason, "refund_ref": payment.refund_ref},
        ip=ip,
    )
    await db.flush()
    return payment


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)
