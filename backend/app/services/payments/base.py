"""Card payment gateway interface. Implementations: mock (no payment), stripe_test, stripe_live."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.models import AdTest, Payment, User


@dataclass
class CheckoutResult:
    status: str  # "succeeded" (mock) | "pending" (redirect to Stripe)
    checkout_url: str | None
    session_id: str | None
    payment_intent_id: str | None = None


@dataclass
class RefundResult:
    ok: bool
    reference: str | None
    message: str


class CardGateway(Protocol):
    mode: str

    async def create_checkout(
        self,
        *,
        user: User,
        test: AdTest,
        payment: Payment,
        amount_usd_minor: int,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutResult: ...

    async def refund(self, payment: Payment, reason: str) -> RefundResult: ...

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...
