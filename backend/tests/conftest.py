"""Test configuration: real Postgres (advar_test), real Redis (db 1), mock LLM, mock payments,
in-memory storage and mail, inline queue. The schema comes from the Alembic migration."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

# --- environment must be set before the app is imported ---------------------------------
BASE_DB_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://advar:advar@postgres:5432/advar")
TEST_DB_URL = BASE_DB_URL.rsplit("/", 1)[0] + "/advar_test"
BASE_REDIS = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TEST_REDIS = BASE_REDIS.rsplit("/", 1)[0] + "/1"
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": TEST_DB_URL,
        "REDIS_URL": TEST_REDIS,
        "LLM_PROVIDER": "mock",
        "PAYMENT_MODE": "mock",
        "STORAGE_BACKEND": "memory",
        "MAIL_BACKEND": "memory",
        "QUEUE_BACKEND": "inline",
        "JWT_SECRET": "test-secret",
        "ENGINE_VERSION": os.environ.get("ENGINE_VERSION", "3.2.0"),
        "MANUAL_AUTO_APPROVE_IN_MOCK": "false",
        "LLM_MAX_CONCURRENCY": "16",
        "COOKIE_DOMAIN": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE = BACKEND_DIR / "samples" / "sample_ad.jpg"


async def _ensure_database() -> None:
    admin_url = BASE_DB_URL.rsplit("/", 1)[0] + "/postgres"
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        exists = (await conn.execute(text("SELECT 1 FROM pg_database WHERE datname = 'advar_test'"))).first()
        if not exists:
            await conn.execute(text("CREATE DATABASE advar_test"))
    await engine.dispose()


def _migrate_and_seed() -> None:
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "scripts.seed"], cwd=BACKEND_DIR, env=env, check=True, capture_output=True
    )


@pytest.fixture(scope="session")
def event_loop():  # noqa: ANN201
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def prepared_database(event_loop):  # noqa: ANN001, ANN201
    event_loop.run_until_complete(_ensure_database())
    _migrate_and_seed()
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _flush_redis(prepared_database):  # noqa: ANN001, ANN202
    from app.services.redis_client import get_redis

    await get_redis().flushdb()
    yield


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limits(_flush_redis):  # noqa: ANN001, ANN202
    """Each test starts with fresh rate-limit counters (the limits themselves are tested explicitly)."""
    from app.services.redis_client import get_redis

    r = get_redis()
    keys = [k async for k in r.scan_iter(match="rl:*")]
    if keys:
        await r.delete(*keys)
    yield


@pytest_asyncio.fixture(scope="session")
async def app_instance(prepared_database):  # noqa: ANN001, ANN202
    from app.main import app

    async with app.router.lifespan_context(app):
        yield app


@pytest_asyncio.fixture
async def client(app_instance) -> AsyncIterator[httpx.AsyncClient]:  # noqa: ANN001
    transport = httpx.ASGITransport(app=app_instance)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class Api:
    """Small helper around the HTTP client for the common flows."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.c = client
        self.prefix = "/api/v1"
        self.token: str | None = None

    def h(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def post(self, path: str, json: Any = None, **kw: Any) -> httpx.Response:
        return await self.c.post(self.prefix + path, json=json, headers=self.h(), **kw)

    async def put(self, path: str, json: Any = None) -> httpx.Response:
        return await self.c.put(self.prefix + path, json=json, headers=self.h())

    async def patch(self, path: str, json: Any = None) -> httpx.Response:
        return await self.c.patch(self.prefix + path, json=json, headers=self.h())

    async def get(self, path: str, **kw: Any) -> httpx.Response:
        return await self.c.get(self.prefix + path, headers=self.h(), **kw)

    async def delete(self, path: str) -> httpx.Response:
        return await self.c.delete(self.prefix + path, headers=self.h())

    async def register_and_login(
        self, email: str | None = None, password: str = "secret123", country: str = "TH", verify: bool = True
    ) -> dict[str, Any]:
        from app.services.email_service import get_mailer

        email = email or f"user-{uuid.uuid4().hex[:10]}@example.com"
        r = await self.post(
            "/auth/register", {"email": email, "password": password, "name": "Test User", "country": country}
        )
        assert r.status_code == 201, r.text
        if verify:
            mail = get_mailer().last_to(email)
            assert mail is not None
            token = mail.headers["X-ADVAR-Token"]
            r = await self.post("/auth/verify-email", {"token": token})
            assert r.status_code == 200, r.text
        r = await self.post("/auth/login", {"email": email, "password": password})
        assert r.status_code == 200, r.text
        self.token = r.json()["access_token"]
        return {"email": email, "password": password, "user_id": r.json()["user_id"]}

    async def login_admin(self) -> None:
        from app.config import get_settings

        s = get_settings()
        r = await self.post("/auth/login", {"email": s.SEED_ADMIN_EMAIL, "password": s.SEED_ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        self.token = r.json()["access_token"]

    async def create_profile(
        self, followers: int = 1800, category: str = "restaurant", **overrides: Any
    ) -> dict[str, Any]:
        data = {
            "business_name": "Pla Pao Bang Na",
            "cuisine": "thai",
            "what_you_sell": "charcoal-grilled seafood",
            "price_level": "mid",
            "taste_profile": {"spice": 0.7, "sweet": 0.3, "sour": 0.6, "adventurousness": 0.5},
            "dietary_options": ["none"],
            "customer_mix": ["locals_mostly"],
            "customer_languages": ["th", "en"],
            "followers": followers,
            "review_count": 140,
            "rating": 4.4,
            "months_in_business": 30,
            "location_type": "street",
            "delivery": True,
        }
        data.update(overrides)
        r = await self.post("/profiles", {"name": "Main preset", "category_code": category, "data": data})
        assert r.status_code == 201, r.text
        return r.json()

    async def upload_image(self, test_id: str) -> dict[str, Any]:
        with SAMPLE_IMAGE.open("rb") as fh:
            r = await self.c.post(
                f"{self.prefix}/tests/{test_id}/assets",
                files={"file": ("ad.jpg", fh, "image/jpeg")},
                headers=self.h(),
            )
        assert r.status_code == 201, r.text
        return r.json()

    async def create_ready_test(
        self,
        *,
        country: str = "TH",
        post_type: str = "paid",
        goal: str = "messages",
        budget_minor: int | None = 6000,
        platforms: list[dict[str, Any]] | None = None,
        profile_id: str | None = None,
        tier: str = "standard",
        followers: int = 1800,
        title: str = "Weekend promo",
    ) -> dict[str, Any]:
        """Create a draft test with profile, image, platforms and post settings (not confirmed)."""
        if profile_id is None:
            profile_id = (await self.create_profile(followers=followers))["id"]
        r = await self.post(
            "/tests",
            {
                "title": title,
                "country_code": country,
                "tier_code": tier,
                "ad_copy": {
                    "caption": "สุดสัปดาห์นี้ ลด 20% ทักแชทจองโต๊ะ",
                    "headline": "20% off this weekend",
                    "cta": "send_message",
                },
                "audiences": [
                    {
                        "name": "Locals",
                        "targeting": {
                            "age_min": 18,
                            "age_max": 45,
                            "interests": ["food"],
                            "audience_size": 180000,
                        },
                    }
                ],
            },
        )
        assert r.status_code == 201, r.text
        test = r.json()
        tid = test["id"]
        r = await self.put(f"/tests/{tid}/profile", {"profile_id": profile_id, "mode": "preset"})
        assert r.status_code == 200, r.text
        await self.upload_image(tid)
        r = await self.put(
            f"/tests/{tid}/post",
            {
                "post_type": post_type,
                "goal": goal,
                "budget_minor": budget_minor,
                "currency": "USD",
                "schedule": ({"days": 3} if post_type != "organic" else {"observe_days": 3}),
            },
        )
        assert r.status_code == 200, r.text
        r = await self.put(
            f"/tests/{tid}/platforms",
            platforms
            or [
                {"code": "facebook", "placements": ["feed"], "budget_share": 60},
                {"code": "tiktok", "placements": ["in_feed"], "budget_share": 40},
            ],
        )
        assert r.status_code == 200, r.text
        return r.json()

    async def confirm(self, test_id: str) -> dict[str, Any]:
        r = await self.post(f"/tests/{test_id}/confirm")
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def api(client: httpx.AsyncClient) -> Api:
    return Api(client)


async def run_pending_jobs() -> list[dict[str, Any]]:
    """Drain the inline queue and run the jobs in-process (worker code path)."""
    from app.services.queue import inline_queue
    from app.workers.run_test import run_test_inline

    results = []
    for name, args in inline_queue.drain():
        if name == "run_test":
            results.append(await run_test_inline(uuid.UUID(str(args[0]))))
    return results


@pytest.fixture
def small_tier():  # noqa: ANN201
    """Nothing to do: tests use the seeded tiers; the engine is fast enough with mock reactions."""
    return None
