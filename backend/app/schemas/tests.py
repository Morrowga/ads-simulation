"""Ad test schemas: create/edit, assets, post settings, confirm, progress, report, compare."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import Goal, PostType, ProfileMode, TestStatus


class TargetingIn(BaseModel):
    age_min: int = Field(default=18, ge=13, le=80)
    age_max: int = Field(default=55, ge=13, le=99)
    genders: list[str] = Field(default_factory=lambda: ["f", "m", "other"])
    interests: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=120)
    radius_km: float | None = Field(default=None, ge=0, le=500)
    languages: list[str] = Field(default_factory=list)
    audience_size: int | None = Field(
        default=None, ge=100, description="Estimated real people in the target pool"
    )

    @model_validator(mode="after")
    def _ages(self) -> TargetingIn:
        if self.age_max < self.age_min:
            raise ValueError("age_max must be >= age_min")
        return self


class AudienceIn(BaseModel):
    name: str = Field(default="Main audience", max_length=80)
    kind: str = Field(default="targeted", description="targeted | followers | custom")
    targeting: TargetingIn = Field(default_factory=TargetingIn)


class AdCopyIn(BaseModel):
    caption: str = Field(default="", max_length=2200)
    headline: str = Field(default="", max_length=200)
    cta: str = Field(
        default="learn_more",
        max_length=40,
        description="learn_more|shop_now|send_message|order_now|sign_up|book_now|get_offer|none",
    )
    link_url: str | None = Field(default=None, max_length=500)


class TestCreateIn(BaseModel):
    title: str = Field(default="Untitled test", max_length=160)
    country_code: str = Field(min_length=2, max_length=2)
    tier_code: str = Field(default="standard", max_length=16)
    ad_copy: AdCopyIn = Field(default_factory=AdCopyIn)
    audiences: list[AudienceIn] = Field(default_factory=lambda: [AudienceIn()], min_length=1, max_length=3)

    @field_validator("country_code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class TestUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    tier_code: str | None = Field(default=None, max_length=16)
    ad_copy: AdCopyIn | None = None
    audiences: list[AudienceIn] | None = Field(default=None, min_length=1, max_length=3)


class PlatformSelectionIn(BaseModel):
    code: str = Field(max_length=32)
    placements: list[str] = Field(default_factory=list)
    budget_share: float = Field(default=100.0, ge=0, le=100)


class ScheduleIn(BaseModel):
    start_date: date | None = None
    days: int = Field(default=3, ge=1, le=14, description="Paid/boosted campaign length in days")
    post_at: datetime | None = Field(default=None, description="Organic: when the post goes live")
    observe_days: int = Field(default=3, ge=1, le=7, description="Organic: observation window in days")
    hours: list[int] | None = Field(default=None, description="Optional preferred hours (0-23) for pacing")


class PostSettingsIn(BaseModel):
    post_type: PostType
    goal: Goal
    budget_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    schedule: ScheduleIn = Field(default_factory=ScheduleIn)

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        return v.upper()


class ProfileAttachIn(BaseModel):
    profile_id: uuid.UUID
    mode: ProfileMode = "preset"
    changes: dict[str, Any] = Field(default_factory=dict)
    new_preset_name: str | None = Field(default=None, max_length=120)


class AssetOut(BaseModel):
    id: uuid.UUID
    kind: str
    mime: str
    width: int | None
    height: int | None
    duration_s: float | None
    size_bytes: int
    sha256: str
    url: str | None = Field(default=None, description="Presigned URL valid for a few minutes")
    created_at: datetime


class PlatformSelectionOut(BaseModel):
    code: str
    name: str | None = None
    placements: list[str]
    budget_share: float
    settings_version: int | None = None


class ProfileRefOut(BaseModel):
    profile_id: uuid.UUID | None
    preset_name: str | None
    version: int | None
    mode: str | None
    snapshot: dict[str, Any] | None


class ProgressOut(BaseModel):
    pct: int
    stage: str | None
    label: str | None = None


class TestOut(BaseModel):
    id: uuid.UUID
    title: str
    status: TestStatus
    tier_code: str
    country_code: str
    post_type: PostType
    goal: Goal
    budget_minor: int | None
    currency: str
    schedule: dict[str, Any]
    platforms: list[PlatformSelectionOut]
    audiences: list[dict[str, Any]]
    ad_copy: dict[str, Any]
    assets: list[AssetOut]
    profile: ProfileRefOut
    settings_versions: dict[str, Any]
    cancel_window: bool
    cancel_count: int
    free_restart_available: bool
    rerun_available: bool
    paid_via: str | None
    progress: ProgressOut
    score: float | None
    error: dict[str, Any] | None
    fingerprint: str | None
    engine_version: str | None
    parent_test_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class TestListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: TestStatus
    tier_code: str
    country_code: str
    post_type: PostType
    goal: Goal
    platforms: list[str]
    progress_pct: int
    score: float | None
    created_at: datetime
    finished_at: datetime | None


class SpecCheckOut(BaseModel):
    platform: str
    placement: str | None
    asset_id: uuid.UUID | None
    ok: bool
    message: str


class DuplicateOut(BaseModel):
    is_duplicate: bool
    test_id: uuid.UUID | None
    title: str | None
    score: float | None
    completed_at: datetime | None


class PriceOut(BaseModel):
    tier_code: str
    tier_usd_minor: int
    extra_platforms: int
    extra_platform_usd_minor: int
    total_usd_minor: int
    display: str
    local: dict[str, Any] | None = None


class ConfirmOut(BaseModel):
    summary: dict[str, Any]
    warnings: list[str]
    spec_checks: list[SpecCheckOut]
    duplicate: DuplicateOut | None
    changed_fields: list[str]
    engine_updated: bool
    price: PriceOut
    status: TestStatus
    fingerprint: str


class CancelOut(BaseModel):
    status: TestStatus
    cancel_count: int
    free_restart_available: bool
    message: str


class ProgressSnapshot(BaseModel):
    test_id: uuid.UUID
    status: TestStatus
    stage: str | None
    pct: int
    label: str | None = None
    cancel_window: bool
    runs_done: int = 0
    runs_target: int = 0
    estimate: dict[str, Any] | None = None
    funnel: dict[str, Any] | None = None
    confidence: str | None = None
    last_event: str | None = None
    updated_at: datetime | None = None
    error: dict[str, Any] | None = None


class ReasonOut(BaseModel):
    section: str
    statement: str
    evidence_ids: list[str]
    confidence: float


class EvidenceOut(BaseModel):
    id: str
    type: str
    statement: str
    values: dict[str, Any]
    platform: str | None = None
    audience_idx: int | None = None


class CommentOut(BaseModel):
    archetype: str
    text: str
    topic: str | None
    sentiment: float
    language_group: str
    platform: str
    scenario: str


class ReportOut(BaseModel):
    test_id: uuid.UUID
    title: str
    goal: Goal
    post_type: PostType
    headline_metric: dict[str, Any]
    score: float | None
    summary: dict[str, Any]
    funnel: dict[str, Any]
    segments: dict[str, Any]
    brand_relationship: dict[str, Any]
    timing: dict[str, Any]
    comments: list[CommentOut]
    reasons: list[ReasonOut]
    evidence: list[EvidenceOut]
    audiences: list[dict[str, Any]]
    platforms: list[dict[str, Any]]
    language_groups: list[dict[str, Any]]
    settings_versions: dict[str, Any]
    engine_version: str | None
    note: str
    pdf_available: bool
    created_at: datetime


class ReportPdfOut(BaseModel):
    url: str
    expires_in: int


class CompareOut(BaseModel):
    a: ReportOut
    b: ReportOut
    metrics: list[dict[str, Any]] = Field(description="[{metric, a, b, delta}]")
    differences: list[str]
