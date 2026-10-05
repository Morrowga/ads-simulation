"""GET /health: database, Redis and storage status."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db import get_session_factory
from app.services.redis_client import redis_ok
from app.services.storage import get_storage

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    ok: bool
    env: str
    version: str
    db: bool
    redis: bool
    storage: bool
    llm_provider: str
    payment_mode: str


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    s = get_settings()
    db_ok = False
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
            db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    r_ok = await redis_ok()
    st_ok = await get_storage().health()
    return HealthOut(
        ok=db_ok and r_ok and st_ok,
        env=s.APP_ENV,
        version=s.ENGINE_VERSION,
        db=db_ok,
        redis=r_ok,
        storage=st_ok,
        llm_provider=s.LLM_PROVIDER,
        payment_mode=s.PAYMENT_MODE,
    )
