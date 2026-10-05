"""Auth and user schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.schemas.common import ORMModel

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)+$"
)


def _validate_email(value: str) -> str:
    """Syntax validation; special-use domains such as .local are allowed (seed admin, Mailpit)."""
    value = value.strip()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("value is not a valid e-mail address")
    local, domain = value.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


EmailStr = Annotated[str, AfterValidator(_validate_email)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    locale: str = Field(default="en", max_length=16)


class RegisterOut(BaseModel):
    user_id: uuid.UUID
    email: str
    verification_required: bool = True
    message: str


class VerifyEmailIn(BaseModel):
    token: str


class ResendVerificationIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")
    user_id: uuid.UUID
    role: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class MeOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    email_verified: bool
    locale: str
    country: str | None
    trial_available: bool
    trial_enabled: bool
    created_at: datetime


class MeUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, max_length=16)
    country: str | None = Field(default=None, min_length=2, max_length=2)


class StreamTokenOut(BaseModel):
    stream_token: str
    expires_in: int
    url: str
