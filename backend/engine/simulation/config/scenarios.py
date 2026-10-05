"""Scenario selection: pick the tier's number of scenarios from the active ones that match the test."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from engine.simulation.types import ScenarioSpec

DEFAULT_SCENARIOS: list[dict[str, Any]] = [
    {
        "code": "normal",
        "name": "Normal week",
        "modifiers": {"mood": 0.0, "competition": 1.0, "activity": 1.0},
        "weight": 1.0,
    },
    {
        "code": "busy_week",
        "name": "Busy competition",
        "modifiers": {"mood": -0.1, "competition": 1.6, "activity": 1.0},
        "weight": 0.9,
    },
    {
        "code": "rainy_low",
        "name": "Rainy / low mood",
        "modifiers": {"mood": -0.3, "competition": 1.0, "activity": 1.15},
        "weight": 0.8,
    },
    {
        "code": "payday",
        "name": "Payday",
        "modifiers": {"mood": 0.2, "competition": 1.2, "activity": 1.05, "buy_boost": 0.25},
        "weight": 0.85,
    },
    {
        "code": "sale_season",
        "name": "Sale season",
        "modifiers": {"mood": 0.15, "competition": 1.8, "activity": 1.2, "discount_norm": 1.4},
        "weight": 0.8,
    },
]


def _matches_dates(rules: dict[str, Any] | None, start: date, days: int = 7) -> bool:
    """date_rules: {"months": [4], "days_of_month": [25,30], "date_ranges": [{"from": "04-12", "to": "04-16"}], "weekdays": [5,6]}"""
    if not rules:
        return True
    window = [start + timedelta(days=i) for i in range(max(1, days))]
    months = rules.get("months")
    if months and not any(d.month in months for d in window):
        return False
    dom = rules.get("days_of_month")
    if dom and not any(d.day in dom for d in window):
        return False
    weekdays = rules.get("weekdays")
    if weekdays and not any(d.weekday() in weekdays for d in window):
        return False
    ranges = rules.get("date_ranges")
    if ranges:
        ok = False
        for r in ranges:
            try:
                fm, fd = (int(x) for x in str(r.get("from", "01-01")).split("-")[:2])
                tm, td = (int(x) for x in str(r.get("to", "12-31")).split("-")[:2])
            except ValueError:
                continue
            for d in window:
                key = (d.month, d.day)
                if (fm, fd) <= key <= (tm, td):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            return False
    return True


def select_scenarios(
    rows: list[dict[str, Any]],
    *,
    country_code: str,
    category_code: str,
    start_date: date,
    n: int,
    days: int = 7,
) -> list[ScenarioSpec]:
    """Filter by active flag, country, category and date rules, then take the `n` highest weights.

    "normal" (or the first scenario) is always included so every test has a baseline.
    """
    rows = rows or DEFAULT_SCENARIOS
    candidates: list[tuple[float, dict[str, Any]]] = []
    for r in rows:
        if r.get("active") is False:
            continue
        if r.get("status", "published") not in ("published", None):
            continue
        cc = r.get("country_codes") or []
        if cc and country_code not in cc:
            continue
        cat = r.get("category_codes") or []
        if cat and category_code not in cat:
            continue
        if not _matches_dates(r.get("date_rules"), start_date, days):
            continue
        candidates.append((float(r.get("weight", 1.0)), r))
    if not candidates:
        candidates = [(float(r.get("weight", 1.0)), r) for r in DEFAULT_SCENARIOS]
    # country-specific scenarios (with a non-empty country filter) get a small bonus so they appear when in season
    ranked = sorted(
        candidates,
        key=lambda x: (-(x[0] + (0.05 if x[1].get("country_codes") else 0.0)), x[1].get("code", "")),
    )
    chosen: list[dict[str, Any]] = []
    baseline = next((r for _, r in ranked if r.get("code") == "normal"), ranked[0][1])
    chosen.append(baseline)
    for _, r in ranked:
        if len(chosen) >= max(1, n):
            break
        if r is baseline or any(c.get("code") == r.get("code") for c in chosen):
            continue
        chosen.append(r)
    return [ScenarioSpec.from_dict(r) for r in chosen]
