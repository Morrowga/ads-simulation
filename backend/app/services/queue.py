"""Job queue abstraction: Arq (Redis) in normal operation, an inline collector in the test suite."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings

log = logging.getLogger("advar.queue")

_pool: ArqRedis | None = None


class InlineQueue:
    """Collects enqueued jobs; tests drain it with `run_pending()`."""

    def __init__(self) -> None:
        self.pending: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue(self, name: str, *args: Any) -> None:
        self.pending.append((name, args))

    def drain(self) -> list[tuple[str, tuple[Any, ...]]]:
        items = list(self.pending)
        self.pending.clear()
        return items


inline_queue = InlineQueue()


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().REDIS_URL)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
    _pool = None


async def enqueue_run(test_id: uuid.UUID) -> str | None:
    s = get_settings()
    if s.QUEUE_BACKEND == "inline":
        await inline_queue.enqueue("run_test", str(test_id))
        return f"inline:{test_id}"
    pool = await get_pool()
    job = await pool.enqueue_job(
        "run_test", str(test_id), _job_id=f"run_test:{test_id}:{uuid.uuid4().hex[:8]}"
    )
    log.info("enqueued run_test test_id=%s job_id=%s", test_id, job.job_id if job else None)
    return job.job_id if job else None
