"""Ad tests and everything produced by the pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk

TEST_STATUSES = (
    "draft",
    "awaiting_payment",
    "payment_review",
    "queued",
    "running",
    "completed",
    "failed",
    "refunded",
)
POST_TYPES = ("paid", "boosted", "organic")
GOALS = ("sales", "messages", "traffic", "awareness", "engagement")
PIPELINE_STAGES = (
    "prepare",
    "analyze_ad",
    "population",
    "archetypes",
    "react",
    "simulate",
    "explain",
    "export",
)


class AdTest(UUIDPk, Timestamps, Base):
    __tablename__ = "ad_tests"
    __table_args__ = (
        Index("ix_tests_user_created", "user_id", text("created_at DESC")),
        Index("ix_tests_status", "status"),
        Index(
            "ix_tests_fingerprint",
            "user_id",
            "fingerprint",
            postgresql_where=text("status = 'completed'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False, default="Untitled test")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    tier_code: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    settings_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    post_type: Mapped[str] = mapped_column(String(16), nullable=False, default="paid")
    goal: Mapped[str] = mapped_column(String(16), nullable=False, default="sales")
    platforms: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    budget_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    audiences: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    ad_copy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id", ondelete="SET NULL"), nullable=True
    )
    profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile_versions.id", ondelete="SET NULL"), nullable=True
    )
    profile_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)  # preset|one_time
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    engine_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cancel_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_window_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paid_via: Mapped[str | None] = mapped_column(String(16), nullable=True)  # trial|stripe|manual|mock
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    free_restart_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rerun_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_test_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="SET NULL"), nullable=True
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    pipeline_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdAsset(UUIDPk, Timestamps, Base):
    __tablename__ = "ad_assets"

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # image|video|frame|audio
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class AdAnalysis(Timestamps, Base):
    __tablename__ = "ad_analyses"

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE"), primary_key=True
    )
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    caption_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    caption_english: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")


class Archetype(UUIDPk, Timestamps, Base):
    __tablename__ = "archetypes"
    __table_args__ = (Index("ix_archetypes_test", "ad_test_id"),)

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE")
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ArchetypeReaction(UUIDPk, Timestamps, Base):
    __tablename__ = "archetype_reactions"

    archetype_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("archetypes.id", ondelete="CASCADE"), unique=True
    )
    reaction: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    fallback_from: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class RunResult(UUIDPk, Timestamps, Base):
    __tablename__ = "run_results"
    __table_args__ = (Index("ix_runs_test", "ad_test_id", "audience_idx", "run_no"),)

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE")
    )
    platform_code: Mapped[str] = mapped_column(String(32), nullable=False)
    audience_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_no: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)


class Report(Timestamps, Base):
    __tablename__ = "reports"

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    funnel: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    segments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    brand_relationship: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    comments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    timing: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    audiences: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    platforms: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    language_groups: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    pdf_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")


class CalibrationResult(UUIDPk, Timestamps, Base):
    __tablename__ = "calibration_results"

    ad_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_tests.id", ondelete="CASCADE")
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")  # csv|manual
    actual_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
