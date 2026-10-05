"""Key/value application settings (settings table) with defaults: score weights, limits,
cancel/restart policy, banned words, Myanmar payment accounts, social links, trial switch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting

DEFAULT_SETTINGS: dict[str, Any] = {
    "trial_enabled": True,
    "trial_tier": "standard",
    "trial_ip_limit_per_day": 3,
    "trial_device_limit_per_day": 2,
    "score_weights_by_goal": {
        "sales": {"stop_rate": 0.20, "ctr": 0.25, "goal_rate": 0.40, "sentiment": 0.15},
        "messages": {"stop_rate": 0.20, "ctr": 0.15, "goal_rate": 0.45, "sentiment": 0.20},
        "traffic": {"stop_rate": 0.25, "goal_rate": 0.55, "sentiment": 0.20},
        "awareness": {"stop_rate": 0.50, "reach_rate": 0.30, "sentiment": 0.20},
        "engagement": {"stop_rate": 0.20, "goal_rate": 0.55, "sentiment": 0.25},
    },
    "rate_limits": {
        "login_per_min_ip": 10,
        "register_per_hour_ip": 5,
        "uploads_per_hour_user": 30,
        "test_starts_per_hour_user": 10,
    },
    "cancel_policy": {"free_restart_once": True, "second_cancel_needs_new_payment": True},
    "banned_words": [
        "should",
        "need to",
        "needs to",
        "change",
        "add",
        "remove",
        "try",
        "recommend",
        "consider",
        "improve",
        "must",
    ],
    "limits": {
        "max_platforms_per_test": 3,
        "max_audiences": 3,
        "max_schedule_days": 14,
        "max_organic_observe_days": 7,
        "budget_warning_multiplier": 3.0,
        "organic_followers_warning": 100,
        "positive_share_alert": 0.6,
    },
    "manual_payment": {
        "accounts": [
            {
                "provider": "KBZPay",
                "account_name": "EXAMPLE ONLY - ADVAR Co.",
                "account_number": "09-000-000-000",
                "note": "Fake example account, replace in admin settings",
            },
            {
                "provider": "WavePay",
                "account_name": "EXAMPLE ONLY - ADVAR Co.",
                "account_number": "09-111-111-111",
                "note": "Fake example account, replace in admin settings",
            },
            {
                "provider": "AYA Bank",
                "account_name": "EXAMPLE ONLY - ADVAR Co.",
                "account_number": "0000-0000-0000-0000",
                "note": "Fake example account, replace in admin settings",
            },
        ],
        "instructions": "Transfer the exact MMK amount, put the payment code in the transfer note, then send a screenshot of the transfer with your payment code to our social media page.",
        "expiry_hours": 48,
    },
    "social_links": {
        "facebook": "https://www.facebook.com/example-advar-page",
        "viber": "https://example.invalid/viber-advar",
        "telegram": "https://t.me/example_advar",
    },
    "report_note": "Results come from a simulation of virtual audiences. They show likely reactions, not guaranteed outcomes.",
    "brand_constants": {"k_month": 40.0, "reviews_factor": 8.0},
    "friend_graph_k": 8,
}


class SettingsCache:
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.loaded_at: datetime | None = None


_cache = SettingsCache()


async def get_all(db: AsyncSession, use_cache: bool = True) -> dict[str, Any]:
    if use_cache and _cache.loaded_at and (datetime.now(UTC) - _cache.loaded_at).total_seconds() < 15:
        return dict(_cache.values)
    res = await db.execute(select(Setting))
    values = dict(DEFAULT_SETTINGS)
    for row in res.scalars().all():
        values[row.key] = row.value
    _cache.values = values
    _cache.loaded_at = datetime.now(UTC)
    return dict(values)


async def get(db: AsyncSession, key: str, default: Any = None) -> Any:
    values = await get_all(db)
    return values.get(key, DEFAULT_SETTINGS.get(key, default))


async def set_many(db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    for key, value in values.items():
        row = await db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value, updated_at=now))
        else:
            row.value = value
            row.updated_at = now
    await db.flush()
    invalidate()
    return await get_all(db, use_cache=False)


async def ensure_defaults(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    res = await db.execute(select(Setting.key))
    existing = {k for (k,) in res.all()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing:
            db.add(Setting(key=key, value=value, updated_at=now))
    await db.flush()
    invalidate()


async def last_updated(db: AsyncSession) -> datetime | None:
    res = await db.execute(select(Setting.updated_at).order_by(Setting.updated_at.desc()).limit(1))
    row = res.first()
    return row[0] if row else None


def invalidate() -> None:
    _cache.loaded_at = None
