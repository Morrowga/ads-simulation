"""Virtual time: hourly ticks with activity, pacing and organic decay per post type."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import numpy as np

from engine.simulation.config.culture import calendar_context
from engine.simulation.config.platforms import peak_hours
from engine.simulation.types import FrozenConfig, PlatformConfig, ScenarioSpec


@dataclass
class Tick:
    t: int
    hour: int
    dow: int
    activity: float  # 0-1 relative online activity this hour (scenario applied)
    impressions: int  # paid impressions to serve this tick (0 for organic)
    organic_factor: float  # organic distribution factor this tick (decayed)
    label: str


def _start_and_hours(cfg: FrozenConfig) -> tuple[datetime, int]:
    sched = cfg.test.schedule or {}
    if cfg.test.post_type == "organic":
        raw = sched.get("post_at")
        start = _parse_dt(raw) or datetime.combine(date.today(), datetime.min.time()).replace(hour=18)
        hours = int(sched.get("observe_days", 3)) * 24
    else:
        raw = sched.get("start_date")
        d = _parse_dt(raw)
        start = (d or datetime.combine(date.today(), datetime.min.time())).replace(hour=0, minute=0)
        hours = int(sched.get("days", 3)) * 24
    return start, max(24, min(hours, 14 * 24))


def _parse_dt(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime.combine(raw, datetime.min.time())
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            try:
                return datetime.combine(date.fromisoformat(raw[:10]), datetime.min.time())
            except ValueError:
                return None
    return None


def total_impressions(
    cfg: FrozenConfig, platform: PlatformConfig, budget_share: float, n_agents: int, scale: float
) -> int:
    """Paid impressions available for this platform, expressed in agent exposures."""
    if cfg.test.post_type == "organic" or not cfg.test.budget_usd:
        return 0
    cpm = max(float(platform.benchmarks.get("cpm_usd", 2.0)), 0.05)
    budget = float(cfg.test.budget_usd) * (budget_share / 100.0)
    real_impressions = budget / cpm * 1000.0
    return int(round(real_impressions / max(scale, 1.0)))


def build_ticks(
    cfg: FrozenConfig,
    platform: PlatformConfig,
    scenario: ScenarioSpec,
    budget_share: float,
    n_agents: int,
    scale: float,
) -> list[Tick]:
    start, hours = _start_and_hours(cfg)
    cal = calendar_context(cfg, start.date(), max(1, hours // 24))
    dow_act = cal["dow_activity"]
    curve = peak_hours(platform)
    preferred = set(int(h) for h in ((cfg.test.schedule or {}).get("hours") or []))
    activities = []
    for t in range(hours):
        hour = (start.hour + t) % 24
        dow = (start.weekday() + (start.hour + t) // 24) % 7
        act = float(curve[hour]) * float(dow_act[dow]) * float(scenario.activity)
        if cal["holidays"]:
            act *= 1.08
        activities.append(min(act, 1.5))
    activities_arr = np.array(activities, dtype=np.float64)

    if cfg.test.post_type in ("paid", "boosted"):
        total = total_impressions(cfg, platform, budget_share, n_agents, scale)
        pacing = activities_arr.copy()
        if preferred:
            for t in range(hours):
                if ((start.hour + t) % 24) not in preferred:
                    pacing[t] *= 0.35
        pacing = pacing / max(pacing.sum(), 1e-9)
        per_tick = np.floor(pacing * total).astype(int)
        remainder = total - int(per_tick.sum())
        if remainder > 0:
            top = np.argsort(-pacing)[:remainder]
            per_tick[top] += 1
    else:
        per_tick = np.zeros(hours, dtype=int)

    half_life = max(float(platform.organic.get("decay_half_life_h", 8.0)), 0.5)
    organic = (
        np.power(0.5, np.arange(hours) / half_life)
        if cfg.test.post_type in ("organic", "boosted")
        else np.zeros(hours)
    )

    ticks = []
    for t in range(hours):
        hour = (start.hour + t) % 24
        dow = (start.weekday() + (start.hour + t) // 24) % 7
        ticks.append(
            Tick(
                t=t,
                hour=hour,
                dow=dow,
                activity=float(activities_arr[t]),
                impressions=int(per_tick[t]),
                organic_factor=float(organic[t]),
                label=f"day {t // 24 + 1} {hour:02d}:00",
            )
        )
    return ticks
