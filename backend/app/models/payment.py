"""Payments, Stripe webhook idempotency, LLM usage, audit logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, _now

PAYMENT_STATUSES = (
    "pending",
    "pending_review",
    "succeeded",
    "failed",
    "cancelled",
    "expired",
    "refunded",
    "consumed",
)
PAYMENT_METHODS = ("trial", "stripe", "manual")


class Payment(UUIDPk, Timestamps, Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index(
            "uq_payment_success_per_test",
            "ad_test_id",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
        ),
        Index(
            "uq_payment_code", "payment_code", unique=True, postgresql_where=text("payment_code IS NOT NULL")
        ),
        Index("ix_payments_review", "status", postgresql_where=text("method = 'manual'")),
        Index("ix_payments_user", "user_id", text("created_at DESC")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # trial|stripe|manual
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="mock"
    )  # mock|stripe_test|stripe_live|manual|trial
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    amount_usd_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    local_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    local_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    payment_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stripe_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. dispute notice
    tier_code: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    platform_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class LLMUsage(UUIDPk, Base):
    __tablename__ = "llm_usage"
    __table_args__ = (Index("ix_llm_usage_test", "ad_test_id"), Index("ix_llm_usage_created", "created_at"))

    ad_test_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="SET NULL"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), default=_now, nullable=False
    )


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity", "entity_id"),)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), default=_now, nullable=False
    )
