"""POST /stripe/webhook: signature-verified, idempotent Stripe event handling (no auth)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.config import get_settings
from app.deps import DB
from app.errors import ApiError, ErrorCode
from app.schemas.payments import StripeWebhookOut
from app.services import payments as payment_service
from app.services.payments import get_gateway

router = APIRouter(prefix="/stripe", tags=["payments"])


@router.post("/webhook", response_model=StripeWebhookOut)
async def stripe_webhook(request: Request, db: DB) -> StripeWebhookOut:
    s = get_settings()
    if s.PAYMENT_MODE == "mock":
        raise ApiError(ErrorCode.stripe_not_configured, "Webhooks are disabled in mock payment mode")
    payload = await request.body()
    event = get_gateway().verify_webhook(payload, request.headers.get("stripe-signature"))
    result = await payment_service.handle_stripe_event(db, event)
    return StripeWebhookOut(**result)
