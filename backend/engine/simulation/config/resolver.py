"""Merge published settings layers into one frozen engine configuration.

Layers, general -> specific (more specific overrides general):
  global defaults and weights  ->  country  ->  platform x country  ->
  category (+ country overrides)  ->  scenarios  ->  business profile

Every input is a plain dict as stored in the database / YAML seed files, so this
module is usable both by the worker and by the command-line engine.
"""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

from engine.simulation.config.scenarios import select_scenarios
from engine.simulation.types import (
    TRAIT_NAMES,
    CategoryConfig,
    CountryConfig,
    FrozenConfig,
    LanguageGroup,
    PlatformConfig,
    PlatformSelection,
    ScenarioSpec,
    TestSpec,
    TierSpec,
    Weights,
)

DEFAULT_BENCHMARKS: dict[str, float] = {
    "stop_rate": 0.12,
    "ctr": 0.010,
    "cvr": 0.020,
    "cpm_usd": 2.0,
    "comment_rate": 0.004,
    "share_rate": 0.003,
    "save_rate": 0.004,
    "message_rate": 0.005,
    "react_rate": 0.03,
    "sentiment": 0.10,
    "buy_rate": 0.0025,
    "engagement_rate": 0.04,
}

DEFAULT_TRAIT_MEANS: dict[str, float] = {
    "patience": 0.45,
    "impulsiveness": 0.5,
    "skepticism": 0.5,
    "anger": 0.3,
    "openness": 0.55,
    "price_sensitivity": 0.6,
    "social": 0.55,
    "brand_loyalty": 0.45,
}

DEFAULT_ORGANIC: dict[str, Any] = {
    "reach_rate_of_followers": 0.06,
    "decay_half_life_h": 8.0,
    "share_boost": 0.3,
    "ranking_engagement_weight": 0.5,
    "source": "estimate_calibrate",
}

DEFAULT_BEHAVIOR: dict[str, Any] = {
    "autoplay": True,
    "sound_default": "off",
    "avg_seconds_per_post": 1.7,
    "hook_window_s": 3.0,
    "fatigue_rate": 0.35,
    "frequency_cap_per_day": 3,
    "sponsored_penalty": 0.25,
    "caption_visibility": 0.8,
}


def deep_merge(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    """Recursive dict merge; values in `override` win. Lists are replaced, not merged."""
    out = copy.deepcopy(base)
    if not override:
        return out
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def strip_sources(value: Any) -> Any:
    """Remove `source` labels so numeric structures are easier to consume."""
    if isinstance(value, dict):
        if set(value.keys()) <= {"value", "source"} and "value" in value:
            return strip_sources(value["value"])
        return {k: strip_sources(v) for k, v in value.items() if k != "source"}
    if isinstance(value, list):
        return [strip_sources(v) for v in value]
    return value


def _float_map(d: dict[str, Any] | None, defaults: dict[str, float]) -> dict[str, float]:
    out = dict(defaults)
    for k, v in (strip_sources(d) or {}).items():
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def build_country(
    code: str, data: dict[str, Any], name: str = "", currency: str = "", version: int | None = None
) -> CountryConfig:
    d = strip_sources(data or {})
    groups = []
    for g in d.get("language_groups", []) or []:
        groups.append(
            LanguageGroup(
                code=str(g.get("code", "en")),
                name=str(g.get("name", g.get("code", "en"))),
                share=float(g.get("share", 0.0)),
                reading_languages=[str(x) for x in g.get("reading_languages", [g.get("code", "en")])],
            )
        )
    if not groups:
        groups = [LanguageGroup("en", "English-speaking", 1.0, ["en"])]
    total = sum(g.share for g in groups) or 1.0
    for g in groups:
        g.share = g.share / total
    languages = [str(x) for x in d.get("languages", [])] or sorted(
        {lang for g in groups for lang in g.reading_languages}
    )
    culture = d.get("culture", {}) or {}
    trait_means = _float_map(culture.get("trait_means"), DEFAULT_TRAIT_MEANS)
    return CountryConfig(
        code=code,
        name=name or str(d.get("name", code)),
        currency=currency or str(d.get("currency", "USD")),
        language_groups=groups,
        languages=languages,
        culture=culture,
        calendar=d.get("calendar", {}) or {},
        demographics=d.get("demographics", {}) or {},
        benchmarks=_float_map(d.get("benchmarks"), DEFAULT_BENCHMARKS),
        trait_means=trait_means,
        version=version,
    )


def build_platform(
    code: str,
    global_config: dict[str, Any],
    markets: dict[str, Any],
    country_code: str,
    name: str = "",
    status: str = "full",
    version: int | None = None,
    country_benchmarks: dict[str, float] | None = None,
) -> PlatformConfig:
    g = strip_sources(global_config or {})
    market = strip_sources((markets or {}).get(country_code) or (markets or {}).get("default") or {})
    behavior = deep_merge(DEFAULT_BEHAVIOR, g.get("behavior", {}))
    behavior = deep_merge(behavior, market.get("behavior", {}))
    organic = deep_merge(DEFAULT_ORGANIC, g.get("organic", {}))
    organic = deep_merge(organic, market.get("organic", {}))
    benchmarks = dict(country_benchmarks or DEFAULT_BENCHMARKS)
    benchmarks.update(_float_map(g.get("benchmarks"), {}))
    benchmarks.update(_float_map(market.get("benchmarks"), {}))
    placements = {}
    for pcode, spec in (g.get("placements", {}) or {}).items():
        placements[pcode] = dict(spec or {})
    supported_goals = {k: list(v) for k, v in (g.get("supported_goals", {}) or {}).items()}
    if not supported_goals:
        supported_goals = {
            "paid": ["sales", "messages", "traffic", "awareness", "engagement"],
            "boosted": ["messages", "traffic", "awareness", "engagement"],
            "organic": ["awareness", "engagement", "messages"],
        }
    return PlatformConfig(
        code=code,
        name=name or str(g.get("name", code.title())),
        status=status,
        placements=placements,
        behavior=behavior,
        organic=organic,
        actions=[str(a) for a in g.get("actions", ["like", "comment", "share", "save", "click", "message"])],
        supported_goals=supported_goals,
        market=market,
        benchmarks=benchmarks,
        version=version,
    )


def build_category(
    code: str, data: dict[str, Any], country_code: str, version: int | None = None
) -> CategoryConfig:
    d = copy.deepcopy(data or {})
    overrides = (d.get("country_overrides") or {}).get(country_code) or {}
    if overrides:
        d = deep_merge(d, overrides)
    return CategoryConfig(
        code=code,
        name=str(d.get("name", code)),
        trait_dimensions=list(d.get("trait_dimensions", []) or []),
        activation_rules=list(d.get("activation_rules", []) or []),
        default_mixes=dict(d.get("default_mixes", {}) or {}),
        buying_behavior=strip_sources(d.get("buying_behavior", {}) or {}),
        blockers=list(d.get("blockers", []) or []),
        trust_signals=list(d.get("trust_signals", []) or []),
        comment_topics=[str(t) for t in d.get("comment_topics", []) or []],
        benchmark_adjustments=_float_map(d.get("benchmark_adjustments"), {}),
        tags=[str(t) for t in d.get("tags", []) or []],
        version=version,
    )


def build_test_spec(test: dict[str, Any], tier: dict[str, Any] | None = None) -> TestSpec:
    t = tier or {}
    tier_spec = TierSpec(
        code=str(t.get("code", "standard")),
        runs_target=int(t.get("runs_target", 150)),
        min_runs=int(t.get("min_runs", 60)),
        scenarios=int(t.get("scenarios", 5)),
        max_audiences=int(t.get("max_audiences", 1)),
        agents=int(t.get("agents", 20000)),
        archetypes=int(t.get("archetypes", 200)),
    )
    platforms = [
        PlatformSelection(
            code=str(p["code"]),
            placements=[str(x) for x in p.get("placements", [])],
            budget_share=float(p.get("budget_share", 100.0)),
            settings_version=p.get("settings_version"),
        )
        for p in test.get("platforms", [])
    ]
    budget_usd = test.get("budget_usd")
    return TestSpec(
        test_id=str(test.get("id", test.get("test_id", "sample"))),
        post_type=str(test.get("post_type", "paid")),
        goal=str(test.get("goal", "sales")),
        budget_usd=float(budget_usd) if budget_usd is not None else None,
        schedule=dict(test.get("schedule", {}) or {}),
        platforms=platforms,
        audiences=list(test.get("audiences", []) or [{"name": "Main audience", "targeting": {}}]),
        tier=tier_spec,
        ad_copy=dict(test.get("ad_copy", {}) or {}),
        title=str(test.get("title", "")),
    )


def resolve(
    *,
    country: dict[str, Any],
    platforms: dict[str, dict[str, Any]],
    category: dict[str, Any],
    scenarios: list[dict[str, Any]],
    weights: dict[str, Any],
    test: dict[str, Any],
    tier: dict[str, Any] | None,
    profile: dict[str, Any] | None,
    settings: dict[str, Any] | None = None,
    today: date | None = None,
) -> FrozenConfig:
    """Build the frozen configuration for one test.

    `country`   : {"code","name","currency","version","data"}
    `platforms` : {code: {"name","status","version","global","markets"}}
    `category`  : {"code","version", ...template fields}
    `scenarios` : list of scenario rows (code, name, modifiers, country_codes, category_codes, date_rules, weight, active)
    `weights`   : {"version","behavior","score_by_goal"}
    `test`      : test dict (post_type, goal, budget_usd, schedule, platforms, audiences, ad_copy)
    """
    settings = settings or {}
    country_cfg = build_country(
        country["code"],
        country.get("data", {}),
        country.get("name", ""),
        country.get("currency", ""),
        country.get("version"),
    )
    category_cfg = build_category(category["code"], category, country_cfg.code, category.get("version"))
    test_spec = build_test_spec(test, tier)

    platform_cfgs: dict[str, PlatformConfig] = {}
    for sel in test_spec.platforms:
        raw = platforms.get(sel.code)
        if raw is None:
            raise ValueError(f"platform settings missing for {sel.code}")
        pc = build_platform(
            sel.code,
            raw.get("global", {}),
            raw.get("markets", {}),
            country_cfg.code,
            name=raw.get("name", ""),
            status=raw.get("status", "full"),
            version=raw.get("version"),
            country_benchmarks=country_cfg.benchmarks,
        )
        # category adjustments multiply the benchmarks (e.g. restaurants: more messages)
        for k, mult in category_cfg.benchmark_adjustments.items():
            if k in pc.benchmarks:
                pc.benchmarks[k] = pc.benchmarks[k] * float(mult)
        platform_cfgs[sel.code] = pc
        sel.settings_version = pc.version

    start = _schedule_start(test_spec.schedule, today)
    chosen = select_scenarios(
        scenarios,
        country_code=country_cfg.code,
        category_code=category_cfg.code,
        start_date=start,
        n=test_spec.tier.scenarios,
    )
    behavior_weights = _float_map((weights or {}).get("behavior"), {})
    score_by_goal = {
        g: {k: float(v) for k, v in (w or {}).items()}
        for g, w in ((weights or {}).get("score_by_goal") or {}).items()
    }
    if settings.get("score_weights_by_goal"):
        for g, w in settings["score_weights_by_goal"].items():
            score_by_goal[g] = {k: float(v) for k, v in w.items()}
    weights_cfg = Weights(
        behavior=behavior_weights, score_by_goal=score_by_goal, version=(weights or {}).get("version")
    )

    versions = {
        "country": {"code": country_cfg.code, "version": country_cfg.version},
        "category": {"code": category_cfg.code, "version": category_cfg.version},
        "platforms": {code: pc.version for code, pc in platform_cfgs.items()},
        "scenarios": [{"code": s.code, "version": _scenario_version(scenarios, s.code)} for s in chosen],
        "weights": weights_cfg.version,
    }
    # trait means may be adjusted by the culture layer of the country
    for t in TRAIT_NAMES:
        country_cfg.trait_means.setdefault(t, DEFAULT_TRAIT_MEANS[t])
    return FrozenConfig(
        country=country_cfg,
        category=category_cfg,
        platforms=platform_cfgs,
        scenarios=chosen,
        weights=weights_cfg,
        test=test_spec,
        profile=dict(profile or {}),
        versions=versions,
        score_benchmarks={code: dict(pc.benchmarks) for code, pc in platform_cfgs.items()},
        settings=settings,
    )


def _scenario_version(rows: list[dict[str, Any]], code: str) -> int | None:
    for r in rows:
        if r.get("code") == code:
            return r.get("version")
    return None


def _schedule_start(schedule: dict[str, Any], today: date | None) -> date:
    today = today or date.today()
    raw = schedule.get("start_date") or schedule.get("post_at")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return today
    return today


def scenario_specs(rows: list[dict[str, Any]]) -> list[ScenarioSpec]:
    return [ScenarioSpec.from_dict(r) for r in rows]
