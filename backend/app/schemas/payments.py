"""Checkout and payment schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import LocalAmountOut, PaymentMethod, PaymentStatus, TestStatus


class CheckoutTierOut(BaseModel):
    code: str
    name: str
    selected: bool
    tier_usd_minor: int
    extra_platforms: int
    extra_platform_usd_minor: int
    total_usd_minor: int
    display: str
    local: LocalAmountOut | None = None


class CheckoutOut(BaseModel):
    test_id: uuid.UUID
    status: TestStatus
    country_code: str
    currency: str
    platforms: list[str]
    tiers: list[CheckoutTierOut]
    selected_tier: str
    total_usd_minor: int
    total_display: str
    local: LocalAmountOut | None
    trial_available: bool
    trial_reason: str | None = None
    methods: list[str] = Field(description="card | trial | manual")
    payment_mode: str = Field(description="mock | stripe_test | stripe_live")
    test_mode_banner: bool


class PaymentOut(BaseModel):
    id: uuid.UUID
    ad_test_id: uuid.UUID
    method: PaymentMethod
    mode: str
    status: PaymentStatus
    amount_usd_minor: int
    currency: str
    local_currency: str | None
    local_amount_minor: int | None
    fx_rate: float | None
    payment_code: str | None
    checkout_url: str | None = None
    admin_reference: str | None
    cancel_reason: str | None
    expires_at: datetime | None
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime


class CardPaymentOut(BaseModel):
    mode: str
    status: PaymentStatus
    payment: PaymentOut
    checkout_url: str | None = None
    test_status: TestStatus


class TrialPaymentOut(BaseModel):
    payment: PaymentOut
    test_status: TestStatus


class ManualAccountOut(BaseModel):
    provider: str
    account_name: str
    account_number: str
    note: str | None = None


class ManualPaymentOut(BaseModel):
    payment: PaymentOut
    test_status: TestStatus
    payment_code: str
    local_currency: str
    local_amount_minor: int
    local_display: str
    usd_display: str
    fx_rate: float
    expires_at: datetime
    accounts: list[ManualAccountOut]
    social_links: dict[str, str]
    instructions: str


class StripeWebhookOut(BaseModel):
    received: bool = True
    event_id: str | None = None
    duplicate: bool = False
    handled: bool = False


class AdminPaymentOut(PaymentOut):
    user_id: uuid.UUID
    user_email: str | None = None
    test_title: str | None = None
    tier_code: str
    platform_count: int
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    refund_ref: str | None
    flagged: str | None
    stripe_session_id: str | None
    stripe_payment_intent_id: str | None


class ApproveIn(BaseModel):
    admin_reference: str | None = Field(default=None, max_length=200)


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RefundIn(BaseModel):
    reason: str = Field(default="", max_length=500)
    manual_refund_reference: str | None = Field(default=None, max_length=200)


class MetricsOut(BaseModel):
    revenue_by_method: dict[str, int]
    revenue_total_usd_minor: int
    ai_cost_usd: float
    gross_margin_usd: float
    gross_margin_pct: float | None
    tests_per_day: list[dict[str, Any]]
    average_approval_time_min: float | None
    failed_tests: int
    completed_tests: int
    pending_manual_orders: int
    llm_spend_today_usd: float
    llm_daily_cap_usd: float
