"""LLM client: provider switch (openai | mock), concurrency, retries, per-test token budget,
daily spend cap and cost logging to llm_usage."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select

from app.config import get_settings
from app.db import session_scope
from app.errors import ApiError, ErrorCode
from app.models import LLMUsage

log = logging.getLogger("advar.llm")


@dataclass
class ProviderResult:
    data: dict[str, Any] | None
    text: str = ""
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    model: str = ""
    invalid_json: bool = False


class Provider(Protocol):
    name: str

    async def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        images: list[bytes] | None,
        context: dict[str, Any] | None,
    ) -> ProviderResult: ...

    async def transcribe(self, *, model: str, audio: bytes, mime: str) -> ProviderResult: ...


class InvalidJSONError(Exception):
    """The model returned invalid JSON twice; the caller falls back to the nearest archetype."""


@dataclass
class UsageTotals:
    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    by_stage: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def cost_for(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """Prices in LLM_PRICE_JSON are USD per 1M tokens; cached input tokens are a subset of input tokens."""
    prices = get_settings().llm_prices.get(model)
    if not prices:
        return 0.0
    uncached = max(input_tokens - cached_tokens, 0)
    return round(
        uncached / 1e6 * prices.get("in", 0.0)
        + cached_tokens / 1e6 * prices.get("cached_in", prices.get("in", 0.0))
        + output_tokens / 1e6 * prices.get("out", 0.0),
        6,
    )


def make_provider() -> Provider:
    s = get_settings()
    if s.LLM_PROVIDER == "mock":
        from app.llm.mock_provider import MockProvider

        return MockProvider()
    from app.llm.openai_provider import OpenAIProvider

    return OpenAIProvider()


async def daily_spend_usd(day: datetime | None = None) -> float:
    day = day or datetime.now(UTC)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_scope() as db:
        res = await db.execute(
            select(func.coalesce(func.sum(LLMUsage.cost_usd), 0)).where(
                LLMUsage.created_at >= start, LLMUsage.created_at < start + timedelta(days=1)
            )
        )
        return float(res.scalar_one() or 0.0)


async def test_spend(test_id: uuid.UUID) -> dict[str, Any]:
    async with session_scope() as db:
        res = await db.execute(
            select(
                func.count(LLMUsage.id),
                func.coalesce(func.sum(LLMUsage.input_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cached_tokens), 0),
                func.coalesce(func.sum(LLMUsage.output_tokens), 0),
                func.coalesce(func.sum(LLMUsage.cost_usd), 0),
            ).where(LLMUsage.ad_test_id == test_id)
        )
        calls, i, c, o, cost = res.one()
        return {
            "calls": int(calls),
            "input_tokens": int(i),
            "cached_tokens": int(c),
            "output_tokens": int(o),
            "cost_usd": float(cost),
        }


class LLMClient:
    """One client per job/test. Thread-safe for asyncio: usage is written in its own session per call."""

    def __init__(
        self, provider: Provider | None = None, test_id: uuid.UUID | None = None, log_usage: bool = True
    ) -> None:
        s = get_settings()
        self.settings = s
        self.provider = provider or make_provider()
        self.test_id = test_id
        self.log_usage = log_usage
        self.semaphore = asyncio.Semaphore(max(1, s.LLM_MAX_CONCURRENCY))
        self.totals = UsageTotals()
        self._daily_checked_at = 0.0
        self._daily_spend = 0.0

    @property
    def is_mock(self) -> bool:
        return self.provider.name == "mock"

    def model_for(self, kind: str) -> str:
        s = self.settings
        return {
            "agent": s.LLM_MODEL_AGENT,
            "smart": s.LLM_MODEL_SMART,
            "transcribe": s.LLM_MODEL_TRANSCRIBE,
        }.get(kind, s.LLM_MODEL_AGENT)

    def ensure_configured(self) -> None:
        if self.provider.name == "openai" and not self.settings.OPENAI_API_KEY:
            raise ApiError(
                ErrorCode.llm_not_configured,
                "OPENAI_API_KEY is empty: set it in .env or use LLM_PROVIDER=mock",
            )

    async def check_budgets(self, force_daily: bool = False) -> None:
        if self.test_id is not None and self.totals.total_tokens > self.settings.LLM_TEST_TOKEN_BUDGET:
            raise ApiError(
                ErrorCode.llm_budget_exceeded,
                f"Token budget of {self.settings.LLM_TEST_TOKEN_BUDGET} per test exceeded",
                details={"tokens": self.totals.total_tokens},
            )
        if self.is_mock:
            return
        now = time.monotonic()
        if force_daily or now - self._daily_checked_at > 60:
            self._daily_spend = await daily_spend_usd()
            self._daily_checked_at = now
        if self._daily_spend + self.totals.cost_usd >= self.settings.DAILY_LLM_SPEND_CAP_USD:
            raise ApiError(
                ErrorCode.llm_daily_cap_reached,
                f"Daily LLM spend cap of ${self.settings.DAILY_LLM_SPEND_CAP_USD:.2f} reached; new tests are paused until tomorrow",
                details={"spend_usd": round(self._daily_spend + self.totals.cost_usd, 4)},
            )

    async def _record(self, stage: str, result: ProviderResult, prompt_version: str) -> None:
        cost = cost_for(result.model, result.input_tokens, result.cached_tokens, result.output_tokens)
        t = self.totals
        t.calls += 1
        t.input_tokens += result.input_tokens
        t.cached_tokens += result.cached_tokens
        t.output_tokens += result.output_tokens
        t.cost_usd = round(t.cost_usd + cost, 6)
        st = t.by_stage.setdefault(stage, {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        st["calls"] += 1
        st["tokens"] += result.input_tokens + result.output_tokens
        st["cost_usd"] = round(st["cost_usd"] + cost, 6)
        if not self.log_usage:
            return
        try:
            async with session_scope() as db:
                db.add(
                    LLMUsage(
                        ad_test_id=self.test_id,
                        stage=stage[:32],
                        model=result.model[:64],
                        input_tokens=result.input_tokens,
                        cached_tokens=result.cached_tokens,
                        output_tokens=result.output_tokens,
                        cost_usd=Decimal(str(cost)),
                        latency_ms=result.latency_ms,
                        prompt_version=prompt_version[:32],
                    )
                )
        except Exception as exc:  # noqa: BLE001 - usage logging must not break a test
            log.warning("llm usage log failed: %s", exc.__class__.__name__)

    async def complete_json(
        self,
        *,
        stage: str,
        kind: str,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float = 0.2,
        images: list[bytes] | None = None,
        context: dict[str, Any] | None = None,
        prompt_version: str = "",
    ) -> dict[str, Any]:
        """Structured completion with retries (429/5xx: 4 attempts with backoff+jitter; invalid JSON: one retry)."""
        self.ensure_configured()
        await self.check_budgets()
        model = self.model_for(kind)
        async with self.semaphore:
            last_exc: Exception | None = None
            json_retries = 0
            for attempt in range(4):
                try:
                    result = await self.provider.complete_json(
                        model=model,
                        system=system,
                        user=user,
                        schema_name=schema_name,
                        schema=schema,
                        temperature=temperature,
                        images=images,
                        context=context,
                    )
                except RetryableError as exc:
                    last_exc = exc
                    await asyncio.sleep(_backoff(attempt))
                    continue
                await self._record(stage, result, prompt_version)
                if result.invalid_json or result.data is None:
                    json_retries += 1
                    if json_retries > 1:
                        raise InvalidJSONError(f"invalid JSON from {model} for {schema_name}")
                    continue
                return result.data
            raise ApiError(
                ErrorCode.llm_unavailable,
                f"LLM unavailable after retries: {last_exc.__class__.__name__ if last_exc else 'unknown'}",
            )

    async def transcribe(self, *, stage: str, audio: bytes, mime: str = "audio/mpeg") -> str:
        self.ensure_configured()
        await self.check_budgets()
        model = self.model_for("transcribe")
        async with self.semaphore:
            for attempt in range(4):
                try:
                    result = await self.provider.transcribe(model=model, audio=audio, mime=mime)
                except RetryableError:
                    await asyncio.sleep(_backoff(attempt))
                    continue
                await self._record(stage, result, "transcribe")
                return result.text
        raise ApiError(ErrorCode.llm_unavailable, "Transcription unavailable after retries")


class RetryableError(Exception):
    """Raised by providers for 429 / 5xx / connection errors."""


def _backoff(attempt: int) -> float:
    import random

    return min(30.0, (2**attempt) * 0.8 + random.uniform(0, 0.6))
