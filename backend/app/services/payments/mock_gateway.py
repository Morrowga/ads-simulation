"""Mock card gateway: no payment needed. POST /pay/card succeeds immediately (local development and tests)."""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import ApiError, ErrorCode
from app.models import AdTest, Payment, User
from app.services.payments.base import CheckoutResult, RefundResult


class MockGateway:
    mode = "mock"

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
        session_id = f"mock_cs_{uuid.uuid4().hex[:16]}"
        return CheckoutResult(
            status="succeeded",
            checkout_url=None,
            session_id=session_id,
            payment_intent_id=f"mock_pi_{uuid.uuid4().hex[:16]}",
        )

    async def refund(self, payment: Payment, reason: str) -> RefundResult:
        return RefundResult(
            ok=True,
            reference=f"mock_re_{uuid.uuid4().hex[:12]}",
            message="Mock refund recorded (no money moved)",
        )

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        raise ApiError(ErrorCode.stripe_not_configured, "Webhooks are not used in mock payment mode")
