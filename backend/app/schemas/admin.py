"""Admin schemas: tests, users, prices, settings, settings editors, sandbox, metrics."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import PlatformStatus, TestStatus
from app.schemas.payments import MetricsOut


class AdminTestListItem(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None
    title: str
    status: TestStatus
    tier_code: str
    country_code: str
    post_type: str
    goal: str
    platforms: list[str]
    progress_pct: int
    stage: str | None
    score: float | None
    paid_via: str | None
    cost_usd: float
    created_at: datetime
    finished_at: datetime | None


class StageInfoOut(BaseModel):
    stage: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    detail: dict[str, Any] | None = None


class AdminTestOut(AdminTestListItem):
    stages: list[StageInfoOut]
    cost_breakdown: list[dict[str, Any]]
    llm_calls: int
    tokens: dict[str, int]
    errors: list[dict[str, Any]]
    settings_versions: dict[str, Any]
    payment: dict[str, Any] | None
    cancel_count: int
    audit: list[dict[str, Any]]


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    email_verified: bool
    country: str | None
    is_blocked: bool
    trial_used: bool
    tests_count: int
    created_at: datetime
    deleted_at: datetime | None


class AdminUserPatchIn(BaseModel):
    is_blocked: bool | None = None
    reset_trial: bool | None = None
    role: str | None = Field(default=None, pattern="^(user|admin)$")


class PriceItemOut(BaseModel):
    tier_code: str
    currency: str
    amount_minor: int
    extra_platform_minor: int
    active: bool


class PricesOut(BaseModel):
    currency: str
    items: list[PriceItemOut]


class PriceItemIn(BaseModel):
    tier_code: str
    amount_minor: int = Field(ge=0)
    extra_platform_minor: int | None = Field(default=None, ge=0)
    active: bool = True


class PricesIn(BaseModel):
    items: list[PriceItemIn]
    change_note: str = ""


class AppSettingsOut(BaseModel):
    values: dict[str, Any]
    updated_at: datetime | None


class AppSettingsIn(BaseModel):
    values: dict[str, Any]
    change_note: str = ""


class VersionedCreateIn(BaseModel):
    """Create a new draft version. `data` shape depends on the kind."""

    code: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=200)
    data: dict[str, Any] = Field(default_factory=dict)
    change_note: str = Field(default="", max_length=1000)


class VersionedUpdateIn(BaseModel):
    """Edit a draft version in place, or (from a published one) start a new draft."""

    name: str | None = Field(default=None, max_length=200)
    data: dict[str, Any]
    change_note: str = Field(default="", max_length=1000)


class PublishIn(BaseModel):
    change_note: str = Field(default="", max_length=1000)


class RollbackIn(BaseModel):
    to_version: int | None = Field(default=None, description="Version to re-publish (default: previous)")
    change_note: str = Field(default="", max_length=1000)


class CountryAdminOut(BaseModel):
    code: str
    name: str
    currency: str
    payment_methods: list[str]
    active: bool
    current_version: int | None
    versions: list[dict[str, Any]]


class CountryUpsertIn(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str
    currency: str = Field(min_length=3, max_length=3)
    payment_methods: list[str] = Field(default_factory=lambda: ["card"])
    active: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    change_note: str = ""


class PlatformAdminOut(BaseModel):
    code: str
    name: str
    status: PlatformStatus
    active: bool
    current_version: int | None
    versions: list[dict[str, Any]]


class PlatformUpsertIn(BaseModel):
    name: str | None = None
    status: PlatformStatus | None = None
    active: bool | None = None
    global_config: dict[str, Any] | None = Field(default=None, alias="global")
    markets: dict[str, Any] | None = None
    sources: dict[str, Any] | None = None
    change_note: str = ""

    model_config = {"populate_by_name": True}


class WeightsOut(BaseModel):
    version: int
    status: str
    behavior: dict[str, Any]
    score_by_goal: dict[str, Any]
    change_note: str
    versions: list[dict[str, Any]]


class WeightsIn(BaseModel):
    behavior: dict[str, Any]
    score_by_goal: dict[str, Any]
    change_note: str = ""
    publish: bool = False


class FxRateIn(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    rate_per_usd: float = Field(gt=0)
    effective_date: date | None = None
    note: str = ""


class FxRatesIn(BaseModel):
    rates: list[FxRateIn]


class CategoryDraftAiIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str | None = Field(default=None, max_length=64)
    parent_code: str | None = None
    hints: str = Field(default="", max_length=2000)


class SandboxRunIn(BaseModel):
    sample: str = Field(default="sample_test.json", description="File name in backend/samples/")
    country_code: str | None = None
    category_code: str | None = None
    platform_codes: list[str] | None = None
    post_type: str | None = None
    goal: str | None = None
    use_drafts: bool = True
    use_real_llm: bool = False
    runs: int = Field(default=20, ge=4, le=150)
    agents: int = Field(default=5000, ge=500, le=50000)
    overrides: dict[str, Any] = Field(
        default_factory=dict, description="Inline settings overrides (draft data)"
    )


class SandboxResultOut(BaseModel):
    draft_versions: dict[str, Any]
    published_versions: dict[str, Any]
    draft_result: dict[str, Any]
    published_result: dict[str, Any]
    comparison: list[dict[str, Any]]
    llm_provider: str
    elapsed_ms: int
    note: str | None = None


class AdminMetricsOut(MetricsOut):
    """Admin dashboard metrics (same shape as MetricsOut, named for the frontend)."""
