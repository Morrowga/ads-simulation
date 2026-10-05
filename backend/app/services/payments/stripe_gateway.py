"""Stripe Checkout (test or live keys). Confirmation happens only through the verified webhook."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import stripe

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, Payment, User
from app.services.payments.base import CheckoutResult, RefundResult


class StripeGateway:
    def __init__(self, mode: str) -> None:
        self.mode = mode
        s = get_settings()
        if not s.STRIPE_SECRET_KEY:
            raise ApiError(ErrorCode.stripe_not_configured, "STRIPE_SECRET_KEY is not set")
        self._key = s.STRIPE_SECRET_KEY
        self._webhook_secret = s.STRIPE_WEBHOOK_SECRET

    async def _call(self, fn, **kwargs):  # noqa: ANN001
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, api_key=self._key, **kwargs))

    async def create_checkout(
        self,
        *,
        user: User,
        test: AdTest,
        payment: Payment,
        amount_usd_minor: int,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult:
        s = get_settings()
        try:
            session = await self._call(
                stripe.checkout.Session.create,
                mode="payment",
                customer_email=user.email,
                client_reference_id=str(payment.id),
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": int(amount_usd_minor),
                            "product_data": {
                                "name": f"{s.APP_NAME} {test.tier_code} test: {test.title[:80]}"
                            },
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"payment_id": str(payment.id), "ad_test_id": str(test.id), "user_id": str(user.id)},
                payment_intent_data={"metadata": {"payment_id": str(payment.id), "ad_test_id": str(test.id)}},
                success_url=success_url,
                cancel_url=cancel_url,
                idempotency_key=f"payment-{payment.id}",
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            raise ApiError(
                ErrorCode.internal_error,
                f"Stripe error: {exc.user_message or exc.__class__.__name__}",
                status_code=502,
            )
        return CheckoutResult(
            status="pending",
            checkout_url=session.url,
            session_id=session.id,
            payment_intent_id=session.payment_intent if isinstance(session.payment_intent, str) else None,
        )

    async def refund(self, payment: Payment, reason: str) -> RefundResult:
        if not payment.stripe_payment_intent_id:
            return RefundResult(
                ok=False, reference=None, message="No payment intent recorded for this payment"
            )
        try:
            refund = await self._call(
                stripe.Refund.create,
                payment_intent=payment.stripe_payment_intent_id,
                metadata={"reason": reason[:200]},
                idempotency_key=f"refund-{payment.id}",
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            return RefundResult(
                ok=False,
                reference=None,
                message=f"Stripe refund failed: {exc.user_message or exc.__class__.__name__}",
            )
        return RefundResult(ok=True, reference=refund.id, message="Refund created in Stripe")

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not self._webhook_secret:
            raise ApiError(ErrorCode.stripe_not_configured, "STRIPE_WEBHOOK_SECRET is not set")
        if not signature:
            raise ApiError(ErrorCode.stripe_signature_invalid, "Missing Stripe-Signature header")
        try:
            event = stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError):  # type: ignore[attr-defined]
            raise ApiError(ErrorCode.stripe_signature_invalid, "Invalid Stripe signature")
        return event.to_dict() if hasattr(event, "to_dict") else dict(event)
