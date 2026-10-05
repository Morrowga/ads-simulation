"""Admin sandbox: run a sample test with draft settings (mock or real LLM) and compare with published."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.llm import tasks as llm_tasks
from app.llm.client import LLMClient
from app.llm.mock_provider import MockProvider
from app.services import settings_versions
from engine.simulation.reaction.priors import priors_from_reactions
from engine.simulation.pipeline import (
    build_population_and_archetypes,
    priors_for_all_scenarios,
    simulate_platform_audience,
    summarize,
)
from engine.simulation.config.resolver import deep_merge
from engine.simulation.types import AdFeatures, FrozenConfig

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"


def load_sample(name: str) -> dict[str, Any]:
    safe = Path(name).name
    path = SAMPLES_DIR / safe
    if not path.exists():
        raise ApiError(
            ErrorCode.not_found,
            f"Sample {safe} not found",
            details={"available": sorted(p.name for p in SAMPLES_DIR.glob("*.json"))},
        )
    return json.loads(path.read_text(encoding="utf-8"))


async def _config(
    db: AsyncSession,
    sample: dict[str, Any],
    *,
    use_drafts: bool,
    runs: int,
    agents: int,
    overrides: dict[str, Any],
    country_code: str | None,
    category_code: str | None,
    platform_codes: list[str] | None,
    post_type: str | None,
    goal: str | None,
) -> FrozenConfig:
    test = dict(sample["test"])
    test["id"] = f"sandbox-{uuid.uuid4().hex[:8]}"
    if platform_codes:
        share = round(100.0 / len(platform_codes), 4)
        test["platforms"] = [{"code": c, "placements": [], "budget_share": share} for c in platform_codes]
    if post_type:
        test["post_type"] = post_type
        if post_type == "organic":
            test["budget_usd"] = None
            test["schedule"] = {"post_at": None, "observe_days": 3}
    if goal:
        test["goal"] = goal
    country = country_code or test.get("country_code", "TH")
    category = category_code or sample.get("profile", {}).get("category_code", "restaurant")
    tier_override = {
        "runs_target": runs,
        "min_runs": min(runs, 20),
        "agents": agents,
        "archetypes": max(10, min(200, agents // 50)),
    }
    cfg = await settings_versions.resolve_for_test(
        db,
        test=test,
        country_code=country,
        category_code=category,
        tier_code=test.get("tier_code", "standard"),
        profile=sample.get("profile", {}).get("data", {}),
        use_drafts=use_drafts,
        tier_override=tier_override,
    )
    if overrides:
        # inline overrides on the resolved layers (draft data typed into the admin form)
        if "weights" in overrides:
            cfg.weights.behavior = deep_merge(cfg.weights.behavior, overrides["weights"].get("behavior", {}))
            cfg.weights.score_by_goal = deep_merge(
                cfg.weights.score_by_goal, overrides["weights"].get("score_by_goal", {})
            )
        if "platform" in overrides:
            for pc in cfg.platforms.values():
                pc.behavior = deep_merge(pc.behavior, overrides["platform"].get("behavior", {}))
                pc.organic = deep_merge(pc.organic, overrides["platform"].get("organic", {}))
                pc.benchmarks.update(
                    {k: float(v) for k, v in overrides["platform"].get("benchmarks", {}).items()}
                )
        if "country" in overrides:
            cfg.country.culture = deep_merge(cfg.country.culture, overrides["country"].get("culture", {}))
            cfg.country.benchmarks.update(
                {k: float(v) for k, v in overrides["country"].get("benchmarks", {}).items()}
            )
    return cfg


async def _run(cfg: FrozenConfig, ad: AdFeatures, client: LLMClient | None) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    out: dict[str, Any] = {"platforms": {}}
    for sel in cfg.test.platforms:
        pop, table = await loop.run_in_executor(None, build_population_and_archetypes, cfg, sel.code, 0)
        if client is None:
            priors = priors_for_all_scenarios(table, ad, cfg, sel.code)
        else:
            priors = {}
            for sc in cfg.scenarios:
                reactions, _v, _f = await llm_tasks.react_archetypes(
                    client,
                    cfg,
                    ad,
                    table,
                    sel.code,
                    sel.placements[0] if sel.placements else "feed",
                    sc,
                    str(cfg.test.ad_copy.get("caption", "")),
                )
                priors[sc.code] = priors_from_reactions(reactions, table.k)
        runs = await loop.run_in_executor(
            None, lambda: simulate_platform_audience(cfg, ad, pop, priors, sel.code, 0, sel.budget_share)
        )
        agg = summarize(runs, cfg.test.goal)
        out["platforms"][sel.code] = {
            "runs": agg["runs"],
            "score": agg["score"],
            "goal_value": agg["goal_value"],
            "rates": {k: v["p50"] for k, v in agg["rates"].items()},
            "funnel": agg["funnel"],
            "blockers": agg["blockers"],
            "fatigue": agg["fatigue"].get("stop_rate_by_exposure"),
            "archetypes": table.k,
            "population": pop.n,
        }
    return out


def _flatten(result: dict[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    for code, r in result.get("platforms", {}).items():
        if r.get("score"):
            flat[f"{code}.score_p50"] = float(r["score"]["p50"])
        if r.get("goal_value"):
            flat[f"{code}.goal_value_p50"] = float(r["goal_value"]["p50"])
        for k, v in (r.get("rates") or {}).items():
            flat[f"{code}.{k}"] = float(v)
    return flat


async def run_sandbox(db: AsyncSession, params: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    t0 = time.perf_counter()
    sample = load_sample(params.get("sample") or "sample_test.json")
    ad = AdFeatures.from_dict(sample.get("ad_features", {}))
    common = dict(
        runs=int(params.get("runs", 20)),
        agents=int(params.get("agents", 5000)),
        overrides=params.get("overrides") or {},
        country_code=params.get("country_code"),
        category_code=params.get("category_code"),
        platform_codes=params.get("platform_codes"),
        post_type=params.get("post_type"),
        goal=params.get("goal"),
    )
    draft_cfg = await _config(db, sample, use_drafts=bool(params.get("use_drafts", True)), **common)
    note = None
    try:
        published_cfg = await _config(db, sample, use_drafts=False, **{**common, "overrides": {}})
    except ApiError as exc:
        # a draft-only category or country has no published counterpart: compare against the
        # published baseline (the sample's own category / country) and say so
        if exc.code not in (
            ErrorCode.category_not_found,
            ErrorCode.settings_not_published,
            ErrorCode.country_not_active,
        ):
            raise
        published_cfg = await _config(
            db,
            sample,
            use_drafts=False,
            **{**common, "overrides": {}, "category_code": None, "country_code": None},
        )
        note = f"no published version for the draft settings ({exc.message}); published side uses the sample baseline"
    client: LLMClient | None = None
    if params.get("use_real_llm") and s.LLM_PROVIDER == "openai" and s.OPENAI_API_KEY:
        client = LLMClient(test_id=None)
    elif params.get("use_real_llm"):
        client = LLMClient(provider=MockProvider(), test_id=None, log_usage=False)
    draft_result = await _run(draft_cfg, ad, client)
    published_result = await _run(published_cfg, ad, client)
    fd, fp = _flatten(draft_result), _flatten(published_result)
    comparison = []
    for key in sorted(set(fd) | set(fp)):
        a, b = fp.get(key), fd.get(key)
        comparison.append(
            {
                "metric": key,
                "published": a,
                "draft": b,
                "delta": (b - a) if a is not None and b is not None else None,
                "relative": ((b - a) / a) if a and b is not None else None,
            }
        )
    return {
        "draft_versions": draft_cfg.versions,
        "published_versions": published_cfg.versions,
        "draft_result": draft_result,
        "published_result": published_result,
        "comparison": comparison,
        "llm_provider": client.provider.name if client else "heuristic",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "note": note,
    }
