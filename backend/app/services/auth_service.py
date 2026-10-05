"""Authentication: register, e-mail verification, login, refresh rotation, logout, password reset,
account update and deletion. No FastAPI imports."""

from __future__ import annotations

import re
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import AdTest, BusinessProfile, EmailToken, RefreshToken, TrialGrant, User
from app.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    now_utc,
    verify_password,
)
from app.services import email_service, settings_service

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)


def normalize_email(email: str) -> str:
    """Lower-case; for gmail-style addresses drop dots and +tags so one person cannot farm trials."""
    email = email.strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if domain in ("gmail.com", "googlemail.com"):
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    else:
        local = local.split("+", 1)[0]
    return f"{local}@{domain}"


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email.strip()))
    return res.scalar_one_or_none()


async def register(
    db: AsyncSession, *, email: str, password: str, name: str, country: str | None, locale: str
) -> tuple[User, str]:
    normalized = normalize_email(email)
    existing = await db.execute(
        select(User).where((User.email == email.strip()) | (User.email_normalized == normalized))
    )
    if existing.scalar_one_or_none() is not None:
        raise ApiError(ErrorCode.email_taken, "An account with this e-mail already exists")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ApiError(ErrorCode.validation_error, "Password must contain letters and numbers")
    user = User(
        email=email.strip(),
        email_normalized=normalized,
        password_hash=hash_password(password),
        name=name.strip(),
        role="user",
        locale=locale or "en",
        country=country.upper() if country else None,
    )
    db.add(user)
    await db.flush()
    token = await issue_email_token(db, user, "verify", VERIFY_TTL)
    return user, token


async def issue_email_token(db: AsyncSession, user: User, purpose: str, ttl: timedelta) -> str:
    token = new_opaque_token(24)
    db.add(
        EmailToken(user_id=user.id, purpose=purpose, token_hash=hash_token(token), expires_at=now_utc() + ttl)
    )
    await db.flush()
    return token


async def consume_email_token(db: AsyncSession, token: str, purpose: str) -> User:
    res = await db.execute(
        select(EmailToken).where(EmailToken.token_hash == hash_token(token), EmailToken.purpose == purpose)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise ApiError(ErrorCode.invalid_token, "Invalid or already used token")
    if row.used_at is not None:
        raise ApiError(ErrorCode.invalid_token, "Token already used")
    if row.expires_at < now_utc():
        raise ApiError(ErrorCode.token_expired, "Token expired")
    row.used_at = now_utc()
    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise ApiError(ErrorCode.invalid_token, "Account not found")
    return user


async def verify_email(db: AsyncSession, token: str) -> User:
    user = await consume_email_token(db, token, "verify")
    if user.email_verified_at is None:
        user.email_verified_at = now_utc()
    await db.flush()
    return user


async def resend_verification(db: AsyncSession, email: str) -> str | None:
    user = await get_user_by_email(db, email)
    if user is None or user.deleted_at is not None or user.email_verified_at is not None:
        return None
    return await issue_email_token(db, user, "verify", VERIFY_TTL)


async def login(
    db: AsyncSession, *, email: str, password: str, user_agent: str | None, ip: str | None
) -> tuple[User, str, str]:
    user = await get_user_by_email(db, email)
    if user is None or user.deleted_at is not None or not verify_password(password, user.password_hash):
        raise ApiError(ErrorCode.invalid_credentials, "Wrong e-mail or password")
    if user.is_blocked:
        raise ApiError(ErrorCode.account_blocked, "This account is blocked")
    access = create_access_token(user.id, user.role)
    refresh = await issue_refresh_token(db, user, user_agent, ip)
    return user, access, refresh


async def issue_refresh_token(db: AsyncSession, user: User, user_agent: str | None, ip: str | None) -> str:
    s = get_settings()
    token = new_opaque_token(32)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(token),
            user_agent=(user_agent or "")[:500],
            ip=(ip or "")[:64],
            expires_at=now_utc() + timedelta(days=s.JWT_REFRESH_TTL_DAYS),
        )
    )
    await db.flush()
    return token


async def refresh(
    db: AsyncSession, token: str, user_agent: str | None, ip: str | None
) -> tuple[User, str, str]:
    """Rotate: revoke the presented token and issue a new pair."""
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
    row = res.scalar_one_or_none()
    if row is None:
        raise ApiError(ErrorCode.invalid_token, "Invalid refresh token", status_code=401)
    if row.revoked_at is not None:
        # re-use of a revoked token: revoke the whole family for safety
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now_utc())
        )
        raise ApiError(ErrorCode.invalid_token, "Refresh token was already used", status_code=401)
    if row.expires_at < now_utc():
        raise ApiError(ErrorCode.token_expired, "Refresh token expired", status_code=401)
    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None:
        raise ApiError(ErrorCode.invalid_token, "Account not found", status_code=401)
    if user.is_blocked:
        raise ApiError(ErrorCode.account_blocked, "This account is blocked")
    row.revoked_at = now_utc()
    access = create_access_token(user.id, user.role)
    new_refresh = await issue_refresh_token(db, user, user_agent, ip)
    return user, access, new_refresh


async def logout(db: AsyncSession, token: str | None) -> None:
    if not token:
        return
    await db.execute(
        update(RefreshToken).where(RefreshToken.token_hash == hash_token(token)).values(revoked_at=now_utc())
    )


async def forgot_password(db: AsyncSession, email: str) -> str | None:
    user = await get_user_by_email(db, email)
    if user is None or user.deleted_at is not None:
        return None
    return await issue_email_token(db, user, "reset", RESET_TTL)


async def reset_password(db: AsyncSession, token: str, password: str) -> User:
    user = await consume_email_token(db, token, "reset")
    user.password_hash = hash_password(password)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now_utc())
    )
    await db.flush()
    return user


async def trial_available(db: AsyncSession, user: User) -> tuple[bool, bool]:
    """(available, enabled): one trial per account, e-mail must be verified, feature switch in settings."""
    enabled = bool(await settings_service.get(db, "trial_enabled", True))
    if not enabled:
        return False, False
    res = await db.execute(select(func.count()).select_from(TrialGrant).where(TrialGrant.user_id == user.id))
    used = int(res.scalar_one() or 0) > 0
    return (not used) and user.email_verified_at is not None, True


async def update_me(
    db: AsyncSession, user: User, *, name: str | None, locale: str | None, country: str | None
) -> User:
    if name is not None:
        user.name = name.strip()
    if locale is not None:
        user.locale = locale
    if country is not None:
        user.country = country.upper()
    await db.flush()
    return user


async def delete_me(db: AsyncSession, user: User) -> None:
    """Soft delete + anonymise: personal data is removed, tests and payments are kept for accounting."""
    stamp = uuid.uuid4().hex[:12]
    user.email = f"deleted-{stamp}@deleted.invalid"
    user.email_normalized = f"deleted-{stamp}@deleted.invalid"
    user.name = "Deleted user"
    user.password_hash = None
    user.deleted_at = now_utc()
    user.is_blocked = True
    await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=now_utc()))
    await db.execute(
        update(BusinessProfile)
        .where(BusinessProfile.user_id == user.id, BusinessProfile.archived_at.is_(None))
        .values(archived_at=now_utc())
    )
    await db.execute(
        update(AdTest)
        .where(AdTest.user_id == user.id, AdTest.status.in_(["draft", "awaiting_payment"]))
        .values(title="Deleted")
    )
    await db.flush()


async def send_verification_mail(user: User, token: str) -> None:
    await email_service.send_verification(user.email, token)
