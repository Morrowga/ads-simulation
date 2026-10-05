"""Category templates (versioned, admin-maintained) and business profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class CategoryTemplate(UUIDPk, Timestamps, Base):
    __tablename__ = "category_templates"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_category_code_version"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    trait_dimensions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    activation_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    default_mixes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    buying_behavior: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    trust_signals: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    comment_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    typical_goals: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    analyzer_hints: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    benchmark_adjustments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    calendar: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    restrictions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    country_overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "parent_code": self.parent_code,
            "tags": self.tags,
            "version": self.version,
            "status": self.status,
            "questions": self.questions,
            "trait_dimensions": self.trait_dimensions,
            "activation_rules": self.activation_rules,
            "default_mixes": self.default_mixes,
            "buying_behavior": self.buying_behavior,
            "blockers": self.blockers,
            "trust_signals": self.trust_signals,
            "comment_topics": self.comment_topics,
            "typical_goals": self.typical_goals,
            "analyzer_hints": self.analyzer_hints,
            "benchmark_adjustments": self.benchmark_adjustments,
            "calendar": self.calendar,
            "restrictions": self.restrictions,
            "country_overrides": self.country_overrides,
        }


class BusinessProfile(UUIDPk, Timestamps, Base):
    __tablename__ = "business_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProfileVersion(UUIDPk, Timestamps, Base):
    __tablename__ = "profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_profile_version"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_profiles.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
