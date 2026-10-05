"""Calibration harness: run the engine (no DB, no LLM) over fixture ads and print a comparison table.

Scoring matches the live pipeline: every fixture ad is compared with an average-quality reference version of
itself (same audience, seed, scenario) after the reference has been anchored to the platform benchmarks.

python -m engine.simulation.calibration.run_calibration [--runs 12] [--agents 4000] [--platform facebook] [--json out.json]
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
from pathlib import Path
from typing import Any

from engine.cli import config_from_sample, load_sample
from engine.data_loader import load_all
from engine.simulation.pipeline import (
    build_population_and_archetypes,
    calibrate_bias,
    priors_for_all_scenarios,
    reference_ad,
    simulate_platform_audience,
    summarize,
)
from engine.simulation.types import AdFeatures

HERE = Path(__file__).resolve().parent
SAMPLE_PATH = HERE.parent.parent.parent / "samples" / "sample_test.json"
FIXTURES_PATH = HERE / "fixtures.json"


def load_fixtures() -> list[dict[str, Any]]:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


def run_fixtures(
    runs: int = 12, agents: int = 4000, platform: str | None = None,
    sample: dict[str, Any] | None = None, fixtures: list[dict[str, Any]] | None = None,
    weight_overrides: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    sample = copy.deepcopy(sample or load_sample(SAMPLE_PATH))
    if platform:
        sample["test"]["platforms"] = [{"code": platform, "placements": ["feed"], "budget_share": 100}]
    data = load_all()
    cfg = config_from_sample(sample, data, runs=runs, agents=agents)
    if weight_overrides:
        cfg.weights.behavior = {**cfg.weights.behavior, **weight_overrides}
    sel = cfg.test.platforms[0]
    pop, table = build_population_and_archetypes(cfg, sel.code, 0)  # same population for every ad
    rows: list[dict[str, Any]] = []
    for fx in (fixtures or load_fixtures()):
        feats = {**sample.get("ad_features", {}), **fx["ad"]}
        ad = AdFeatures.from_dict(feats)
        priors = priors_for_all_scenarios(table, ad, cfg, sel.code)
        # Reference ad + benchmark anchoring, exactly as the worker does it.
        ref_ad = reference_ad(ad)
        ref_priors = priors_for_all_scenarios(table, ref_ad, cfg, sel.code)
        bias = calibrate_bias(cfg, ref_ad, pop, ref_priors, sel.code, 0, sel.budget_share)
        run_list = simulate_platform_audience(
            cfg, ad, pop, priors, sel.code, 0, sel.budget_share,
            ref_ad=ref_ad, ref_priors_by_scenario=ref_priors, bias=bias,
        )
        agg = summarize(run_list, cfg.test.goal)
        r = agg["rates"]
        ref_buys = [m["reference"]["buy_rate"] for m in run_list if m.get("reference")]
        rows.append(
            {
                "name": fx["name"],
                "expect": fx["expect"],
                "score": agg["score"]["p50"],
                "score_p10": agg["score"]["p10"],
                "score_p90": agg["score"]["p90"],
                "stop": r["stop_rate"]["p50"],
                "ctr": r["ctr"]["p50"],
                "buy": r["buy_rate"]["p50"],
                "engagement": r["engagement_rate"]["p50"],
                "ref_buy": statistics.median(ref_buys) if ref_buys else None,
                "bias": bias,
                "runs": agg["runs"],
            }
        )
    return rows


def print_table(rows: list[dict[str, Any]], bench: dict[str, float] | None = None) -> None:
    print(
        f"\n{'ad':<18}{'expect':<7}{'score':>7}{'p10':>7}{'p90':>7}{'stop':>8}{'ctr':>8}{'buy':>8}{'eng':>8}"
        f"{'refbuy':>8}{'runs':>6}"
    )
    for x in rows:
        print(
            f"{x['name']:<18}{x['expect']:<7}{x['score']:>7.1f}{x['score_p10']:>7.1f}{x['score_p90']:>7.1f}"
            f"{x['stop']:>8.3f}{x['ctr']:>8.4f}{x['buy']:>8.4f}{x['engagement']:>8.4f}"
            f"{(x.get('ref_buy') or 0.0):>8.4f}{x['runs']:>6}"
        )
    by: dict[str, list[float]] = {}
    for x in rows:
        by.setdefault(x["expect"], []).append(x["score"])
    print("\nmean score by expectation:", {k: round(sum(v) / len(v), 1) for k, v in by.items()})
    if "low" in by and "high" in by:
        print(f"spread high - low: {sum(by['high']) / len(by['high']) - sum(by['low']) / len(by['low']):.1f}  (target >= 30)")
    if bench:
        print("benchmarks:", {k: bench.get(k) for k in ("stop_rate", "ctr", "buy_rate", "engagement_rate")})


def main() -> int:
    ap = argparse.ArgumentParser(prog="engine.simulation.calibration.run_calibration")
    ap.add_argument("--runs", type=int, default=12)
    ap.add_argument("--agents", type=int, default=4000)
    ap.add_argument("--platform", default=None)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args()
    sample = load_sample(SAMPLE_PATH)
    if args.platform:
        sample["test"]["platforms"] = [{"code": args.platform, "placements": ["feed"], "budget_share": 100}]
    cfg = config_from_sample(sample, runs=args.runs, agents=args.agents)
    bench = cfg.platforms[cfg.test.platforms[0].code].benchmarks
    rows = run_fixtures(args.runs, args.agents, args.platform, sample)
    print_table(rows, bench)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())