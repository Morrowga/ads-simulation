"""Checkout and payment endpoints for a test."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.deps import DB, Client, CurrentUser
from app.schemas.payments import (
    CardPaymentOut,
    CheckoutOut,
    ManualAccountOut,
    ManualPaymentOut,
    TrialPaymentOut,
)
from app.services import fx, serializers
from app.services import payments as payment_service

router = APIRouter(prefix="/tests", tags=["checkout"])


@router.get("/{test_id}/checkout", response_model=CheckoutOut)
async def checkout(test_id: uuid.UUID, db: DB, user: CurrentUser) -> CheckoutOut:
    return CheckoutOut(**await payment_service.checkout_info(db, user, test_id))


@router.post("/{test_id}/pay/trial", response_model=TrialPaymentOut)
async def pay_trial(test_id: uuid.UUID, db: DB, user: CurrentUser, client: Client) -> TrialPaymentOut:
    payment, test = await payment_service.pay_with_trial(db, user, test_id, client.ip, client.device_hash)
    return TrialPaymentOut(payment=serializers.payment_out(payment), test_status=test.status)


@router.post("/{test_id}/pay/card", response_model=CardPaymentOut)
async def pay_card(test_id: uuid.UUID, db: DB, user: CurrentUser, client: Client) -> CardPaymentOut:
    payment, test, url = await payment_service.pay_with_card(db, user, test_id, client.ip)
    return CardPaymentOut(
        mode=payment.mode,
        status=payment.status,
        payment=serializers.payment_out(payment),
        checkout_url=url,
        test_status=test.status,
    )


@router.post("/{test_id}/pay/manual", response_model=ManualPaymentOut)
async def pay_manual(test_id: uuid.UUID, db: DB, user: CurrentUser, client: Client) -> ManualPaymentOut:
    payment, test, info = await payment_service.pay_manual(db, user, test_id, client.ip)
    return ManualPaymentOut(
        payment=serializers.payment_out(payment),
        test_status=test.status,
        payment_code=payment.payment_code or "",
        local_currency=payment.local_currency or "",
        local_amount_minor=payment.local_amount_minor or 0,
        local_display=info["local_display"],
        usd_display=fx.format_money(payment.amount_usd_minor, "USD"),
        fx_rate=float(payment.fx_rate or 0),
        expires_at=payment.expires_at,
        accounts=[
            ManualAccountOut(**{k: v for k, v in a.items() if k in ManualAccountOut.model_fields})
            for a in info["accounts"]
        ],
        social_links={str(k): str(v) for k, v in (info["social_links"] or {}).items()},
        instructions=info["instructions"],
    )
