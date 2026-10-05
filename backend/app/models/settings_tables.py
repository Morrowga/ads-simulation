"""Admin-controlled, versioned settings: countries, platforms, scenarios, weights, tiers, prices, fx, settings."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class Country(Timestamps, Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_methods: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CountryVersion(UUIDPk, Timestamps, Base):
    __tablename__ = "country_versions"
    __table_args__ = (UniqueConstraint("country_code", "version", name="uq_country_version"),)

    country_code: Mapped[str] = mapped_column(String(2), ForeignKey("countries.code", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft"
    )  # draft|published|archived
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FxRate(UUIDPk, Timestamps, Base):
    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    rate_per_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Tier(Timestamps, Base):
    __tablename__ = "tiers"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    runs_target: Mapped[int] = mapped_column(Integer, nullable=False)
    min_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    scenarios: Mapped[int] = mapped_column(Integer, nullable=False)
    max_audiences: Mapped[int] = mapped_column(Integer, nullable=False)
    agents: Mapped[int] = mapped_column(Integer, nullable=False)
    archetypes: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Price(UUIDPk, Timestamps, Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("tier_code", "currency", name="uq_price_tier_currency"),)

    tier_code: Mapped[str] = mapped_column(String(16), nullable=False)  # quick|standard|full|extra_platform
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    extra_platform_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="any")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Platform(Timestamps, Base):
    __tablename__ = "platforms"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planned")  # full|beta|planned
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PlatformSettings(UUIDPk, Timestamps, Base):
    __tablename__ = "platform_settings"
    __table_args__ = (UniqueConstraint("platform_code", "version", name="uq_platform_version"),)

    platform_code: Mapped[str] = mapped_column(String(32), ForeignKey("platforms.code", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    global_config: Mapped[dict[str, Any]] = mapped_column("global", JSONB, nullable=False, default=dict)
    markets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Scenario(UUIDPk, Timestamps, Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_scenario_code_version"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    modifiers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    country_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    category_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    date_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeightSet(UUIDPk, Timestamps, Base):
    __tablename__ = "weight_sets"
    __table_args__ = (UniqueConstraint("version", name="uq_weight_set_version"),)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    behavior: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score_by_goal: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    change_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
