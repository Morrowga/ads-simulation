"""Synchronous orchestration helpers shared by the worker, the sandbox and the CLI."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

import numpy as np

from engine.simulation.results.aggregate import aggregate_runs, run_batch_estimate, should_stop
from engine.simulation.population.archetypes import build_archetypes
from engine.simulation.runtime.montecarlo import run_seed, simulate_run
from engine.simulation.population.builder import build_population
from engine.simulation.reaction.priors import heuristic_reaction, priors_from_reactions
from engine.simulation.results.scoring import score_run
from engine.simulation.types import AdFeatures, ArchetypeTable, FrozenConfig, Population, ReactionPriors, ScenarioSpec

log = logging.getLogger(__name__)

BatchCallback = Callable[[list[dict[str, Any]], list[dict[str, Any]], bool], bool]
"""on_batch(batch_runs, all_runs, finished) -> continue?  Returning False cancels the loop."""

# Reference ad: the same ad (language, offer, price, cta, taste, tags) but with average creative quality.
# The score compares the real ad with this reference on the SAME audience, seed and scenario, so audience
# warmth, culture and offer context cancel out and only creative quality moves the score.
REFERENCE_QUALITY: dict[str, float] = {
    "hook_strength": 0.5,
    "novelty": 0.5,
    "genericness": 0.5,
    "visual_quality": 0.5,
    "caption_strength": 0.5,
    "clarity": 0.6,
}
REFERENCE_KEYS = (
    "stop_rate",
    "ctr",
    "buy_rate",
    "cvr",
    "message_rate",
    "engagement_rate",
    "react_rate",
    "comment_rate",
    "share_rate",
    "save_rate",
)
REFERENCE_FLOOR = 0.25  # reference rate never drops below 25% of the platform benchmark (avoids divide-by-tiny)

# Benchmark anchoring: logit offsets that make the reference ad land exactly on the market benchmark.
BIAS_TARGETS = {
    "stop": "stop_rate",
    "click": "ctr",
    "message": "message_rate",
    "buy": "buy_rate",
    "react": "engagement_rate",
}
CAL_SEEDS = 3
CAL_ITERS = 8
CAL_DAMP = 0.6 # fraction of the logit gap closed per iteration (stops over-shooting between coupled rates)


def reference_ad(ad: AdFeatures) -> AdFeatures:
    """The same ad with average creative quality (hook, novelty, genericness, visual, caption, clarity)."""
    return AdFeatures.from_dict({**ad.to_dict(), **REFERENCE_QUALITY})


def reference_bench(ref_rates: dict[str, Any], bench: dict[str, float]) -> dict[str, float]:
    """Benchmarks for score_run built from the reference run: parity with the reference scores 50."""
    out = dict(bench)
    for key in REFERENCE_KEYS:
        if key not in ref_rates:
            continue
        floor = REFERENCE_FLOOR * float(bench.get(key, 0.0) or 0.0)
        out[key] = max(float(ref_rates[key] or 0.0), floor, 1e-6)
    return out


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def calibrate_bias(
    cfg: FrozenConfig,
    ref_ad: AdFeatures,
    pop: Population,
    ref_priors_by_scenario: dict[str, ReactionPriors],
    platform_code: str,
    audience_idx: int,
    budget_share: float,
) -> dict[str, float]:
    """Find logit offsets so that the average-quality reference ad hits the platform/market benchmark
    (stop, ctr, message, buy, engagement) on this audience. Deterministic: fixed calibration seeds."""
    bench = cfg.platforms[platform_code].benchmarks
    scenario = next((s for s in cfg.scenarios if s.code == "normal"), cfg.scenarios[0])
    priors = ref_priors_by_scenario.get(scenario.code) or next(iter(ref_priors_by_scenario.values()))
    bias = {name: 0.0 for name in BIAS_TARGETS}
    for it in range(CAL_ITERS):
        acc = {rate_key: 0.0 for rate_key in BIAS_TARGETS.values()}
        for j in range(CAL_SEEDS):
            seed = run_seed(cfg.test.test_id, platform_code, audience_idx, -2 - j)
            m = simulate_run(pop, ref_ad, priors, cfg, platform_code, scenario, seed, budget_share, bias=bias)
            for rate_key in acc:
                acc[rate_key] += float(m["rates"].get(rate_key, 0.0)) / CAL_SEEDS
        for name, rate_key in BIAS_TARGETS.items():
            target = float(bench.get(rate_key, 0.0) or 0.0)
            if target <= 0.0:
                continue
            step = CAL_DAMP * (_logit(target) - _logit(acc[rate_key]))
            bias[name] = float(np.clip(bias[name] + step, -6.0, 6.0))
        log.debug(
            "CAL sc=%s it=%d %s bias=%s",
            scenario.code,
            it,
            " ".join(f"{k}={acc[v]:.5f}/{float(bench.get(v, 0.0) or 0.0):.5f}" for k, v in BIAS_TARGETS.items()),
            {k: round(v, 3) for k, v in bias.items()},
        )
    return {k: round(v, 4) for k, v in bias.items()}


def population_seed(test_id: str, platform_code: str, audience_idx: int) -> int:
    return run_seed(test_id, platform_code, audience_idx, -1)


def build_population_and_archetypes(
    cfg: FrozenConfig,
    platform_code: str,
    audience_idx: int,
    n_agents: int | None = None,
    k: int | None = None,
) -> tuple[Population, ArchetypeTable]:
    audience = (
        cfg.test.audiences[audience_idx]
        if audience_idx < len(cfg.test.audiences)
        else {"name": "Main audience", "targeting": {}}
    )
    n = int(n_agents or cfg.test.tier.agents)
    seed = population_seed(cfg.test.test_id, platform_code, audience_idx)
    pop = build_population(cfg, platform_code, audience, n, seed)
    table = build_archetypes(pop, int(k or cfg.test.tier.archetypes), seed)
    return pop, table


def heuristic_reactions(
    table: ArchetypeTable, ad: AdFeatures, scenario: ScenarioSpec, platform_code: str, post_type: str
) -> list[dict[str, Any]]:
    return [heuristic_reaction(profile, ad, scenario, platform_code, post_type) for profile in table.profiles]


def simulate_platform_audience(
    cfg: FrozenConfig,
    ad: AdFeatures,
    pop: Population,
    priors_by_scenario: dict[str, ReactionPriors],
    platform_code: str,
    audience_idx: int,
    budget_share: float,
    on_batch: BatchCallback | None = None,
    runs_target: int | None = None,
    min_runs: int | None = None,
    batch_size: int = 5,
    existing_runs: list[dict[str, Any]] | None = None,
    ref_ad: AdFeatures | None = None,
    ref_priors_by_scenario: dict[str, ReactionPriors] | None = None,
    bias: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Monte Carlo loop with the stopping rule. Runs cycle through the scenarios so each batch of
    5 covers all 5 scenarios (5 x 30 = 150 for the Standard tier).

    When ref_ad and ref_priors_by_scenario are given, every run is also simulated with the reference ad
    (same seed) and the score is measured against that reference instead of the absolute benchmarks.
    `bias` (from calibrate_bias) shifts the decision logits so an average ad matches the benchmark."""
    target = int(runs_target or cfg.test.tier.runs_target)
    minimum = int(min_runs or cfg.test.tier.min_runs)
    scenarios = cfg.scenarios
    runs: list[dict[str, Any]] = list(existing_runs or [])
    bench = cfg.platforms[platform_code].benchmarks
    use_reference = ref_ad is not None and bool(ref_priors_by_scenario)
    run_no = len(runs)
    while run_no < target:
        batch = []
        for _ in range(batch_size):
            if run_no >= target:
                break
            scenario = scenarios[run_no % len(scenarios)]
            priors = priors_by_scenario.get(scenario.code) or next(iter(priors_by_scenario.values()))
            seed = run_seed(cfg.test.test_id, platform_code, audience_idx, run_no)
            m = simulate_run(pop, ad, priors, cfg, platform_code, scenario, seed, budget_share, bias=bias)
            run_bench = bench
            if use_reference:
                ref_priors = ref_priors_by_scenario.get(scenario.code) or next(
                    iter(ref_priors_by_scenario.values())
                )
                ref_m = simulate_run(
                    pop, ref_ad, ref_priors, cfg, platform_code, scenario, seed, budget_share, bias=bias
                )
                run_bench = reference_bench(ref_m["rates"], bench)
                m["reference"] = {k: ref_m["rates"].get(k) for k in REFERENCE_KEYS}
            if bias:
                m["calibration_bias"] = dict(bias)
            m["run_no"] = run_no
            m["audience_idx"] = audience_idx
            m["score"] = score_run(m, cfg.test.goal, run_bench, cfg.weights.score_by_goal)
            batch.append(m)
            runs.append(m)
            run_no += 1
        stop_now = should_stop(runs, minimum) or run_no >= target
        if on_batch is not None:
            cont = on_batch(batch, runs, stop_now)
            if cont is False:
                break
        if stop_now:
            break
    return runs


def summarize(runs: list[dict[str, Any]], goal: str) -> dict[str, Any]:
    agg = aggregate_runs(runs, goal)
    agg["estimate"] = run_batch_estimate(runs, goal)
    return agg


def priors_for_all_scenarios(
    table: ArchetypeTable, ad: AdFeatures, cfg: FrozenConfig, platform_code: str
) -> dict[str, ReactionPriors]:
    out = {}
    for sc in cfg.scenarios:
        reactions = heuristic_reactions(table, ad, sc, platform_code, cfg.test.post_type)
        out[sc.code] = priors_from_reactions(reactions, table.k)
    return out