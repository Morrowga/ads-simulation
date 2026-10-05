"""Shared response shapes: errors, pagination, enums."""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

TestStatus = Literal[
    "draft", "awaiting_payment", "payment_review", "queued", "running", "completed", "failed", "refunded"
]
PostType = Literal["paid", "boosted", "organic"]
Goal = Literal["sales", "messages", "traffic", "awareness", "engagement"]
PlatformStatus = Literal["full", "beta", "planned"]
VersionStatus = Literal["draft", "published", "archived"]
PaymentMethod = Literal["trial", "stripe", "manual"]
PaymentStatus = Literal[
    "pending", "pending_review", "succeeded", "failed", "cancelled", "expired", "refunded", "consumed"
]
ProfileMode = Literal["preset", "one_time", "update_preset", "new_preset"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorOut(BaseModel):
    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class OkOut(BaseModel):
    ok: bool = True
    message: str | None = None


class MoneyOut(BaseModel):
    amount_minor: int
    currency: str
    display: str = Field(description="Formatted amount, e.g. '$12.00' or '= ฿420'")


class LocalAmountOut(BaseModel):
    currency: str
    amount_minor: int
    fx_rate: float
    approximate: bool = True
    display: str
