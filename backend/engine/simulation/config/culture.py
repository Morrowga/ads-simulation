"""Culture layer: adjusts trait means, trust-signal weights, tone sensitivity and calendar effects."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

from engine.simulation.types import TRAIT_NAMES, CountryConfig, FrozenConfig

DEFAULT_TRUST_WEIGHTS = {
    "reviews": 0.8,
    "free_shipping": 0.6,
    "cash_on_delivery": 0.5,
    "official_store": 0.6,
    "local_language": 0.5,
    "celebrity": 0.4,
    "price_shown": 0.6,
    "location_shown": 0.5,
    "guarantee": 0.6,
    "photos_of_real_product": 0.7,
    "photos_of_real_food": 0.7,
    "verified_badge": 0.5,
    "phone_number": 0.4,
}


def trait_means_vector(country: CountryConfig) -> np.ndarray:
    return np.array([float(country.trait_means.get(t, 0.5)) for t in TRAIT_NAMES], dtype=np.float32)


def trait_correlation() -> np.ndarray:
    """Fixed, plausible correlation structure (impulsiveness vs patience negative, etc.)."""
    c = np.eye(len(TRAIT_NAMES), dtype=np.float64)

    def set_(a: str, b: str, v: float) -> None:
        i, j = TRAIT_NAMES.index(a), TRAIT_NAMES.index(b)
        c[i, j] = c[j, i] = v

    set_("patience", "impulsiveness", -0.45)
    set_("patience", "anger", -0.3)
    set_("skepticism", "openness", -0.35)
    set_("skepticism", "brand_loyalty", 0.15)
    set_("impulsiveness", "price_sensitivity", -0.2)
    set_("social", "openness", 0.3)
    set_("anger", "skepticism", 0.25)
    set_("brand_loyalty", "openness", -0.15)
    return c


def trust_weights(cfg: FrozenConfig) -> dict[str, float]:
    """Trust-signal weights: defaults, overridden by country culture, boosted by category trust signals."""
    out = dict(DEFAULT_TRUST_WEIGHTS)
    culture_ts = (cfg.country.culture or {}).get("trust_signals") or {}
    for k, v in culture_ts.items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    for ts in cfg.category.trust_signals:
        code = ts.get("code")
        if code:
            out[code] = max(out.get(code, 0.0), float(ts.get("weight", 0.5)))
    return out


def trust_score(cfg: FrozenConfig, ad_trust_signals: list[str]) -> float:
    """0-1 score of how much trust the ad's visible signals earn in this market."""
    w = trust_weights(cfg)
    if not ad_trust_signals:
        return 0.15
    got = sum(w.get(s, 0.3) for s in ad_trust_signals)
    return float(min(1.0, 0.15 + got / 2.0))


def sponsored_skepticism(cfg: FrozenConfig) -> float:
    return float((cfg.country.culture or {}).get("sponsored_skepticism", 0.5))


def comprehension_penalty(cfg: FrozenConfig) -> float:
    """Factor (0-1) applied to caption effects for agents who cannot read the caption's language."""
    return float((cfg.country.culture or {}).get("comprehension_penalty", 0.4))


def tone_fit(cfg: FrozenConfig, emotional_tone: str) -> float:
    """-0.5..0.5 adjustment from how well the ad's tone matches local preference."""
    tone = (cfg.country.culture or {}).get("tone") or {}
    key = {
        "funny": "humor",
        "humorous": "humor",
        "playful": "humor",
        "formal": "formal",
        "serious": "formal",
        "emotional": "emotional",
        "warm": "emotional",
        "hard_sell": "hard_sell",
        "urgent": "hard_sell",
        "neutral": None,
    }.get(str(emotional_tone).lower())
    if not key:
        return 0.0
    pref = float(tone.get(key, 0.5))
    return float(pref - 0.5)


def calendar_context(cfg: FrozenConfig, start: date, days: int) -> dict[str, Any]:
    """Payday / holiday / season effects for the run window."""
    cal = cfg.country.calendar or {}
    paydays = [int(x) for x in cal.get("paydays", [25, 30])]
    holidays = cal.get("holidays", []) or []
    seasons = cal.get("seasons", []) or []
    window_days = [date.fromordinal(start.toordinal() + i) for i in range(max(1, days))]
    is_payday = any(d.day in paydays or (d.day >= max(paydays) if paydays else False) for d in window_days)
    holiday_names = []
    for h in holidays:
        try:
            m, dd = (int(x) for x in str(h.get("date", "")).split("-")[:2])
        except ValueError:
            continue
        span = int(h.get("days", 1))
        for d in window_days:
            for off in range(span):
                hd = date(d.year, m, dd).toordinal() + off
                if d.toordinal() == hd:
                    holiday_names.append(str(h.get("name", "holiday")))
    mood = 0.0
    for s in seasons:
        months = s.get("months", []) or []
        if any(d.month in months for d in window_days):
            mood += float(s.get("mood", 0.0))
    dow = cal.get("dow_activity") or [1.0, 0.98, 0.97, 1.0, 1.05, 1.12, 1.08]
    return {
        "is_payday": bool(is_payday),
        "holidays": sorted(set(holiday_names)),
        "season_mood": float(mood),
        "dow_activity": [float(x) for x in dow][:7] + [1.0] * max(0, 7 - len(dow)),
    }
