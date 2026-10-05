"""Redis fixed-window rate limits (login 10/min/IP, register 5/h/IP, uploads 30/h/user, test starts 10/h/user)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.errors import ApiError, ErrorCode
from app.services.redis_client import get_redis


@dataclass(frozen=True)
class Limit:
    name: str
    max_hits: int
    window_sec: int


LOGIN = Limit("login", 10, 60)
REGISTER = Limit("register", 5, 3600)
UPLOAD = Limit("upload", 30, 3600)
TEST_START = Limit("test_start", 10, 3600)
FORGOT = Limit("forgot", 5, 3600)
RESEND = Limit("resend", 5, 3600)


async def hit(limit: Limit, key: str) -> tuple[int, int]:
    """Increment the counter; returns (hits, seconds_until_reset)."""
    r = get_redis()
    window = int(time.time() // limit.window_sec)
    rkey = f"rl:{limit.name}:{key}:{window}"
    async with r.pipeline(transaction=True) as pipe:
        pipe.incr(rkey)
        pipe.expire(rkey, limit.window_sec + 1)
        hits, _ = await pipe.execute()
    reset = limit.window_sec - int(time.time() % limit.window_sec)
    return int(hits), reset


async def enforce(limit: Limit, key: str) -> None:
    hits, reset = await hit(limit, key)
    if hits > limit.max_hits:
        raise ApiError(
            ErrorCode.rate_limited,
            f"Too many {limit.name} attempts, try again in {reset} seconds",
            details={"retry_after_sec": reset, "limit": limit.max_hits, "window_sec": limit.window_sec},
        )


async def reset(limit: Limit, key: str) -> None:
    r = get_redis()
    window = int(time.time() // limit.window_sec)
    await r.delete(f"rl:{limit.name}:{key}:{window}")
