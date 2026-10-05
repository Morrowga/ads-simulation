"""FastAPI dependencies: database session, current user, admin guard, client info, pagination."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session_factory
from app.errors import ApiError, ErrorCode
from app.models import User
from app.security import decode_token, device_hash

bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


@dataclass
class ClientInfo:
    ip: str | None
    user_agent: str | None

    @property
    def device_hash(self) -> str:
        return device_hash(self.user_agent, self.ip)


def get_client_info(request: Request) -> ClientInfo:
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    return ClientInfo(ip=ip, user_agent=request.headers.get("user-agent"))


Client = Annotated[ClientInfo, Depends(get_client_info)]


async def get_current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
) -> User:
    if creds is None or not creds.credentials:
        raise ApiError(ErrorCode.unauthorized, "Missing bearer token", status_code=401)
    payload = decode_token(creds.credentials, "access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise ApiError(ErrorCode.invalid_token, "Invalid token subject", status_code=401)
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise ApiError(ErrorCode.unauthorized, "Account not found", status_code=401)
    if user.is_blocked:
        raise ApiError(ErrorCode.account_blocked, "This account is blocked")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ApiError(ErrorCode.forbidden, "Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def require_verified(user: CurrentUser) -> User:
    if user.email_verified_at is None:
        raise ApiError(ErrorCode.email_not_verified, "Verify your e-mail first")
    return user


VerifiedUser = Annotated[User, Depends(require_verified)]


@dataclass
class Pagination:
    cursor: str | None
    limit: int


def get_pagination(
    cursor: str | None = Query(default=None), limit: int = Query(default=20, ge=1, le=100)
) -> Pagination:
    return Pagination(cursor=cursor, limit=limit)


Page = Annotated[Pagination, Depends(get_pagination)]
