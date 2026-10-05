"""Payments: Myanmar manual orders (code uniqueness, approve/cancel/expiry, refused elsewhere, fixed
local amount), Stripe webhook idempotency with fixture events, refunds, local price display."""

from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta

import pytest
import stripe
from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import AdTest, Payment, StripeEvent, User
from app.security import now_utc, payment_code
from app.services import payments as payment_service
from app.services.payments import manual
from app.services.payments.stripe_gateway import StripeGateway
from tests.conftest import Api, run_pending_jobs


def test_payment_code_format_and_uniqueness() -> None:
    codes = {payment_code() for _ in range(2000)}
    assert len(codes) == 2000
    code = payment_code()
    assert code.startswith("ADV-") and len(code) == 13 and not any(ch in code for ch in "0O1I")


@pytest.mark.asyncio
async def test_manual_order_flow_myanmar(api: Api, client) -> None:  # noqa: ANN001
    await api.register_and_login(country="MM")
    test = await api.create_ready_test(
        country="MM",
        tier="quick",
        platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
    )
    tid = test["id"]
    await api.confirm(tid)
    checkout = (await api.get(f"/tests/{tid}/checkout")).json()
    assert checkout["methods"] == ["manual"] or set(checkout["methods"]) == {"manual"}
    assert (
        "card" not in checkout["methods"]
        and checkout["currency"] == "MMK"
        and checkout["local"]["currency"] == "MMK"
    )
    r = await api.post(f"/tests/{tid}/pay/card")
    assert r.status_code == 403 and r.json()["error"]["code"] == "method_not_allowed"

    r = await api.post(f"/tests/{tid}/pay/manual")
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["test_status"] == "payment_review" and order["payment_code"].startswith("ADV-")
    assert (
        order["local_currency"] == "MMK"
        and order["local_amount_minor"] > 0
        and order["accounts"]
        and order["social_links"]
    )
    assert (
        order["local_amount_minor"] == round(500 / 100 * 2100 / 100) * 100
    )  # fixed from the placeholder rate, rounded to 100 kyat
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "payment_review"

    # the local amount stays fixed on the order even if the rate changes afterwards
    admin = Api(client)
    await admin.login_admin()
    r = await admin.put(
        "/admin/fx-rates", {"rates": [{"currency": "MMK", "rate_per_usd": 3000, "note": "test change"}]}
    )
    assert r.status_code == 200
    payment = (await api.get("/payments")).json()["items"][0]
    assert (
        payment["local_amount_minor"] == order["local_amount_minor"] and payment["status"] == "pending_review"
    )

    # admin finds the order by payment code and approves it
    r = await admin.get(f"/admin/payments?code={order['payment_code']}")
    assert (
        r.status_code == 200
        and len(r.json()["items"]) == 1
        and r.json()["items"][0]["payment_code"] == order["payment_code"]
    )
    pid = r.json()["items"][0]["id"]
    r = await admin.post(f"/admin/payments/{pid}/approve", {"admin_reference": "KBZ tx 12345"})
    assert (
        r.status_code == 200
        and r.json()["status"] == "succeeded"
        and r.json()["admin_reference"] == "KBZ tx 12345"
    )
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "queued"
    # approving twice is idempotent
    assert (await admin.post(f"/admin/payments/{pid}/approve")).status_code == 200
    results = await run_pending_jobs()
    assert results[0]["ok"] is True
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "completed"
    # restore the placeholder rate for other tests
    await admin.put(
        "/admin/fx-rates", {"rates": [{"currency": "MMK", "rate_per_usd": 2100, "note": "PLACEHOLDER rate"}]}
    )

    # manual refund needs a reference
    r = await admin.post(f"/admin/payments/{pid}/refund", {"reason": "customer request"})
    assert r.status_code == 422
    r = await admin.post(
        f"/admin/payments/{pid}/refund",
        {"reason": "customer request", "manual_refund_reference": "refund-tx-1"},
    )
    assert r.status_code == 200 and r.json()["status"] == "refunded"
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_manual_order_cancel_and_expiry(api: Api, client) -> None:  # noqa: ANN001
    await api.register_and_login(country="MM")
    test = await api.create_ready_test(
        country="MM",
        tier="quick",
        platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
    )
    tid = test["id"]
    await api.confirm(tid)
    order = (await api.post(f"/tests/{tid}/pay/manual")).json()
    admin = Api(client)
    await admin.login_admin()
    pid = order["payment"]["id"]
    r = await admin.post(f"/admin/payments/{pid}/cancel", {"reason": "no transfer found"})
    assert (
        r.status_code == 200
        and r.json()["status"] == "cancelled"
        and r.json()["cancel_reason"] == "no transfer found"
    )
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "awaiting_payment"
    # a new order gets a new code; the old order cannot be approved
    order2 = (await api.post(f"/tests/{tid}/pay/manual")).json()
    assert order2["payment_code"] != order["payment_code"]
    r = await admin.post(f"/admin/payments/{pid}/approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_invalid_state"
    # expiry job
    async with session_scope() as db:
        p = await db.get(Payment, uuid.UUID(order2["payment"]["id"]))
        p.expires_at = now_utc() - timedelta(hours=1)
    async with session_scope() as db:
        n = await manual.expire_due(db)
    assert n == 1
    assert (await api.get(f"/tests/{tid}")).json()["status"] == "awaiting_payment"
    history = (await api.get("/payments")).json()["items"]
    assert {p["status"] for p in history} == {"cancelled", "expired"}


@pytest.mark.asyncio
async def test_manual_refused_for_non_manual_country(api: Api) -> None:
    await api.register_and_login(country="TH")
    test = await api.create_ready_test(tier="quick")
    await api.confirm(test["id"])
    r = await api.post(f"/tests/{test['id']}/pay/manual")
    assert r.status_code == 403 and r.json()["error"]["code"] == "method_not_allowed"


def _stripe_event(
    event_id: str, etype: str, payment_id: str, test_id: str, amount: int, session_id: str = "cs_test_1"
) -> dict:
    return {
        "id": event_id,
        "object": "event",
        "type": etype,
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "payment_status": "paid",
                "amount_total": amount,
                "payment_intent": "pi_test_1",
                "client_reference_id": payment_id,
                "metadata": {"payment_id": payment_id, "ad_test_id": test_id},
            }
        },
    }


@pytest.mark.asyncio
async def test_stripe_webhook_idempotency_and_signature(api: Api, monkeypatch) -> None:  # noqa: ANN001
    await api.register_and_login(country="US")
    test = await api.create_ready_test(
        country="US",
        tier="quick",
        platforms=[{"code": "facebook", "placements": ["feed"], "budget_share": 100}],
    )
    tid = test["id"]
    await api.confirm(tid)
    # create a pending stripe payment row (as pay/card would in stripe_test mode)
    async with session_scope() as db:
        user = (
            await db.execute(select(User).where(User.id == (await db.get(AdTest, uuid.UUID(tid))).user_id))
        ).scalar_one()
        payment = Payment(
            user_id=user.id,
            ad_test_id=uuid.UUID(tid),
            method="stripe",
            mode="stripe_test",
            status="pending",
            amount_usd_minor=500,
            currency="USD",
            tier_code="quick",
            platform_count=1,
            stripe_session_id="cs_test_1",
        )
        db.add(payment)
        await db.flush()
        pid = str(payment.id)
    event = _stripe_event("evt_1", "checkout.session.completed", pid, tid, 500)
    async with session_scope() as db:
        r1 = await payment_service.handle_stripe_event(db, event)
    assert r1["handled"] is True and r1["duplicate"] is False
    async with session_scope() as db:
        r2 = await payment_service.handle_stripe_event(db, event)
    assert r2["duplicate"] is True and r2["handled"] is False
    async with session_scope() as db:
        p = await db.get(Payment, uuid.UUID(pid))
        t = await db.get(AdTest, uuid.UUID(tid))
        assert p.status == "succeeded" and p.stripe_payment_intent_id == "pi_test_1"
        assert t.status == "queued" and t.paid_via == "stripe"
        assert (await db.get(StripeEvent, "evt_1")).processed_at is not None
    # only one job was enqueued despite the duplicated event
    from app.services.queue import inline_queue

    assert len([j for j in inline_queue.pending if j[1][0] == tid]) == 1
    await run_pending_jobs()
    # refund event
    refund_event = {
        "id": "evt_2",
        "type": "charge.refunded",
        "data": {
            "object": {"id": "ch_1", "payment_intent": "pi_test_1", "refunds": {"data": [{"id": "re_1"}]}}
        },
    }
    async with session_scope() as db:
        r3 = await payment_service.handle_stripe_event(db, refund_event)
    assert r3["handled"] is True
    async with session_scope() as db:
        assert (await db.get(Payment, uuid.UUID(pid))).status == "refunded"
        assert (await db.get(AdTest, uuid.UUID(tid))).status == "refunded"

    # signature verification through the gateway (stripe_test mode with a known webhook secret)
    s = get_settings()
    monkeypatch.setattr(s, "PAYMENT_MODE", "stripe_test")
    monkeypatch.setattr(s, "STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(s, "STRIPE_WEBHOOK_SECRET", "whsec_testsecret")
    gateway = StripeGateway("stripe_test")
    payload = json.dumps(_stripe_event("evt_3", "checkout.session.expired", pid, tid, 500)).encode()
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload.decode()}", "whsec_testsecret")
    header = f"t={ts},v1={sig}"
    parsed = gateway.verify_webhook(payload, header)
    assert parsed["id"] == "evt_3"
    r = await api.c.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers={"stripe-signature": header, "content-type": "application/json"},
    )
    assert r.status_code == 200 and r.json()["event_id"] == "evt_3"
    r = await api.c.post(
        "/api/v1/stripe/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=bad", "content-type": "application/json"},
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "stripe_signature_invalid"
    monkeypatch.setattr(s, "PAYMENT_MODE", "mock")
    r = await api.c.post("/api/v1/stripe/webhook", content=payload, headers={"stripe-signature": header})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_local_price_display_from_fx_rates(api: Api) -> None:
    tiers_th = (await api.get("/tiers?country=TH")).json()
    std = next(t for t in tiers_th if t["code"] == "standard")
    assert (
        std["local"]["currency"] == "THB"
        and std["local"]["approximate"] is True
        and std["local"]["display"].startswith("= ฿")
    )
    assert std["local"]["amount_minor"] == round(12 * 33.5 * 100)
    tiers_mm = (await api.get("/tiers?country=MM&platforms=2")).json()
    std_mm = next(t for t in tiers_mm if t["code"] == "standard")
    assert std_mm["local"]["currency"] == "MMK" and std_mm["local"]["amount_minor"] % 100 == 0
    assert std_mm["extra_platform_local"]["currency"] == "MMK"
    tiers_us = (await api.get("/tiers?country=US")).json()
    assert next(t for t in tiers_us if t["code"] == "quick")["local"] is None
