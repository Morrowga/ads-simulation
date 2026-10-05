"""Business profile schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProfileCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_code: str = Field(min_length=1, max_length=64)
    data: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    data: dict[str, Any]
    is_default: bool | None = None
    change_note: str = ""


class ProfileDuplicateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class ProfileVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    data: dict[str, Any]
    data_hash: str
    created_at: datetime
    tests: list[dict[str, Any]] = Field(
        default_factory=list, description="[{id, title, status}] tests that used it"
    )


class ProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    category_code: str
    category_name: str | None = None
    current_version: int
    is_default: bool
    archived: bool
    data: dict[str, Any]
    summary: str
    created_at: datetime
    updated_at: datetime
