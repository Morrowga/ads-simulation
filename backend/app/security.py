"""Password hashing (Argon2id), JWT access tokens, opaque refresh/e-mail tokens and stream tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings
from app.errors import ApiError, ErrorCode

_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:  # noqa: BLE001 - corrupted hash
        return False


def now_utc() -> datetime:
    return datetime.now(UTC)


def sha256_hex(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def new_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return sha256_hex(token)


# --- JWT access tokens ------------------------------------------------------


def create_access_token(user_id: uuid.UUID, role: str, extra: dict[str, Any] | None = None) -> str:
    s = get_settings()
    now = now_utc()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=s.JWT_ACCESS_TTL_MIN)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, s.JWT_SECRET, algorithm="HS256")


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ApiError(ErrorCode.token_expired, "Token expired", status_code=401)
    except jwt.PyJWTError:
        raise ApiError(ErrorCode.invalid_token, "Invalid token", status_code=401)
    if payload.get("typ") != expected_type:
        raise ApiError(ErrorCode.invalid_token, "Wrong token type", status_code=401)
    return payload


# --- stream tokens (SSE: EventSource cannot send headers) --------------------


def create_stream_token(user_id: uuid.UUID, test_id: uuid.UUID) -> str:
    s = get_settings()
    now = now_utc()
    payload = {
        "sub": str(user_id),
        "test": str(test_id),
        "typ": "stream",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=s.STREAM_TOKEN_TTL_SEC)).timestamp()),
    }
    return jwt.encode(payload, s.JWT_SECRET, algorithm="HS256")


def decode_stream_token(token: str) -> tuple[uuid.UUID, uuid.UUID]:
    payload = decode_token(token, expected_type="stream")
    try:
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["test"])
    except (KeyError, ValueError):
        raise ApiError(ErrorCode.invalid_token, "Invalid stream token", status_code=401)


# --- misc -------------------------------------------------------------------


def payment_code() -> str:
    """Short human-friendly payment code for Myanmar manual orders, e.g. ADV-7K3M-92QX."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
    part = lambda n: "".join(secrets.choice(alphabet) for _ in range(n))  # noqa: E731
    return f"ADV-{part(4)}-{part(4)}"


def device_hash(user_agent: str | None, ip: str | None) -> str:
    return sha256_hex(f"{user_agent or ''}|{ip or ''}")[:32]
