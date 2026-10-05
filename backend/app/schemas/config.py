"""Public configuration schemas: countries, tiers, platforms, categories."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import LocalAmountOut, PlatformStatus, VersionStatus


class LanguageGroupOut(BaseModel):
    code: str
    name: str
    share: float
    reading_languages: list[str]
    source: str | None = None


class CountryOut(BaseModel):
    code: str
    name: str
    currency: str
    payment_methods: list[str]
    languages: list[str]
    language_groups: list[LanguageGroupOut]
    version: int | None
    active: bool


class TierOut(BaseModel):
    code: str
    name: str
    runs_target: int
    min_runs: int
    scenarios: int
    max_audiences: int
    agents: int
    archetypes: int
    price_usd_minor: int
    price_display: str
    extra_platform_usd_minor: int
    extra_platform_display: str
    local: LocalAmountOut | None = None
    extra_platform_local: LocalAmountOut | None = None


class PlacementOut(BaseModel):
    code: str
    formats: list[str]
    ratios: list[str]
    video_s: list[float] | None = None
    max_caption_chars: int | None = None
    source: str | None = None


class PostTypeSupportOut(BaseModel):
    post_type: str
    supported_goals: list[str]


class PlatformOut(BaseModel):
    code: str
    name: str
    status: PlatformStatus
    version: int | None
    placements: list[PlacementOut]
    ad_specs: dict[str, Any]
    post_types: list[PostTypeSupportOut]
    supported_goals: dict[str, list[str]]
    actions: list[str]
    organic: dict[str, Any]


class QuestionOut(BaseModel):
    key: str
    label: str
    type: str
    options: list[Any] | None = None
    required: bool = False
    feeds_trait: str | None = None
    help: str | None = None
    default: Any | None = None
    min: float | None = None
    max: float | None = None


class TraitDimensionOut(BaseModel):
    key: str
    label: str
    kind: str
    values: list[str] | None = None
    default_distribution: dict[str, Any] | None = None


class CategorySummaryOut(BaseModel):
    code: str
    name: str
    parent_code: str | None
    tags: list[str]
    version: int
    typical_goals: list[str]


class CategoryTemplateOut(BaseModel):
    code: str
    name: str
    parent_code: str | None
    tags: list[str]
    version: int
    status: VersionStatus
    questions: list[QuestionOut]
    trait_dimensions: list[TraitDimensionOut]
    activation_rules: list[dict[str, Any]]
    default_mixes: dict[str, Any]
    buying_behavior: dict[str, Any]
    blockers: list[dict[str, Any]]
    trust_signals: list[dict[str, Any]]
    comment_topics: list[str]
    typical_goals: list[str]
    analyzer_hints: dict[str, Any]
    benchmark_adjustments: dict[str, Any]
    calendar: dict[str, Any]
    restrictions: dict[str, Any]
    country_overrides: dict[str, Any]


class ScenarioOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    version: int
    modifiers: dict[str, Any]
    country_codes: list[str]
    category_codes: list[str]
    date_rules: dict[str, Any]
    weight: float
    active: bool
    status: VersionStatus
    change_note: str
    created_by: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime


class FxRateOut(BaseModel):
    currency: str
    rate_per_usd: float
    effective_date: date
    note: str
    updated_at: datetime


class SettingsVersionOut(BaseModel):
    kind: str = Field(description="countries | categories | platforms | scenarios | weights")
    id: str = Field(description="Version row id (uuid) or code for countries/platforms")
    code: str | None = None
    version: int
    status: VersionStatus
    change_note: str
    created_by: uuid.UUID | None
    published_at: datetime | None
    created_at: datetime
    data: dict[str, Any] | None = None
