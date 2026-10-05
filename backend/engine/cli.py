"""Command-line engine runner (no web app, no database, heuristic reactions instead of the LLM).

python -m engine.cli run samples/sample_test.json [--runs 30] [--agents 20000] [--json out.json]
python -m engine.cli bench            # time one 72-tick run over 20,000 agents
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from engine.simulation.results.aggregate import combine_platforms
from engine.data_loader import load_all, tier_by_code
from engine.simulation.results.evidence import EvidenceBuilder, build_evidence
from engine.simulation.pipeline import (
    build_population_and_archetypes,
    priors_for_all_scenarios,
    simulate_platform_audience,
    summarize,
)
from engine.simulation.config.resolver import resolve
from engine.simulation.types import AdFeatures, FrozenConfig


def load_sample(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def config_from_sample(
    sample: dict[str, Any],
    data: dict[str, Any] | None = None,
    runs: int | None = None,
    agents: int | None = None,
) -> FrozenConfig:
    data = data or load_all()
    test = dict(sample["test"])
    country_code = test.get("country_code", "TH")
    country_row = data["countries"][country_code]
    country = {
        "code": country_code,
        "name": country_row["name"],
        "currency": country_row["currency"],
        "version": country_row.get("version", 1),
        "data": country_row["data"],
    }
    category_code = sample.get("profile", {}).get("category_code") or test.get("category_code", "restaurant")
    category = dict(data["categories"][category_code])
    tier = tier_by_code(test.get("tier_code", "standard"))
    if runs:
        tier["runs_target"] = int(runs)
        tier["min_runs"] = min(tier["min_runs"], int(runs))
    if agents:
        tier["agents"] = int(agents)
        tier["archetypes"] = min(tier["archetypes"], max(10, int(agents) // 50))
    platforms = {code: data["platforms"][code] for code in [p["code"] for p in test["platforms"]]}
    return resolve(
        country=country,
        platforms=platforms,
        category=category,
        scenarios=data["scenarios"],
        weights=data["weights"],
        test=test,
        tier=tier,
        profile=sample.get("profile", {}).get("data", {}),
        settings={},
    )


def run_sample(
    sample: dict[str, Any], runs: int | None = None, agents: int | None = None, verbose: bool = True
) -> dict[str, Any]:
    cfg = config_from_sample(sample, runs=runs, agents=agents)
    ad = AdFeatures.from_dict(sample.get("ad_features", {}))
    results: dict[str, Any] = {"platforms": {}, "evidence": [], "versions": cfg.versions}
    builder = EvidenceBuilder()
    shares = {}
    t_all = time.perf_counter()
    for sel in cfg.test.platforms:
        t0 = time.perf_counter()
        pop, table = build_population_and_archetypes(cfg, sel.code, 0)
        t1 = time.perf_counter()
        priors = priors_for_all_scenarios(table, ad, cfg, sel.code)
        t2 = time.perf_counter()

        def on_batch(batch: list[dict[str, Any]], all_runs: list[dict[str, Any]], finished: bool) -> bool:
            if verbose:
                last = batch[-1]
                print(
                    f"  [{sel.code}] run {len(all_runs):3d}  scenario={last['scenario']:<14} score={last['score']:5.1f}  stop={last['rates']['stop_rate']:.3f} ctr={last['rates']['ctr']:.4f} goal={last['goal_value']}",
                    file=sys.stderr,
                )
            return True

        run_list = simulate_platform_audience(
            cfg, ad, pop, priors, sel.code, 0, sel.budget_share, on_batch=on_batch
        )
        t3 = time.perf_counter()
        agg = summarize(run_list, cfg.test.goal)
        ev = build_evidence(agg, priors[cfg.scenarios[0].code], cfg, sel.code, 0, ad.to_dict(), builder)
        results["platforms"][sel.code] = {
            "aggregate": agg,
            "archetypes": table.k,
            "population": pop.n,
            "timing_ms": {
                "population": int((t1 - t0) * 1000),
                "reactions": int((t2 - t1) * 1000),
                "simulation": int((t3 - t2) * 1000),
                "per_run": int((t3 - t2) * 1000 / max(1, len(run_list))),
            },
        }
        results["evidence"] = ev
        shares[sel.code] = sel.budget_share
    results["overall"] = combine_platforms(
        {k: v["aggregate"] for k, v in results["platforms"].items()}, shares
    )
    results["elapsed_ms"] = int((time.perf_counter() - t_all) * 1000)
    return results


def print_summary(results: dict[str, Any], goal: str) -> None:
    print("\n=== ADVAR engine summary ===")
    print(f"goal: {goal}   elapsed: {results['elapsed_ms']} ms   versions: {json.dumps(results['versions'])}")
    for code, r in results["platforms"].items():
        a = r["aggregate"]
        print(
            f"\n[{code}] runs={a['runs']} population={a['population']} archetypes={r['archetypes']}  timing={r['timing_ms']}"
        )
        print(f"  score P10/P50/P90: {a['score']['p10']}/{a['score']['p50']}/{a['score']['p90']}")
        print(
            f"  {a['goal_metric']}: {a['goal_value']['p10']:.0f}/{a['goal_value']['p50']:.0f}/{a['goal_value']['p90']:.0f}"
        )
        print(f"  funnel (P50): {a['funnel']}")
        r_ = a["rates"]
        print(
            f"  stop_rate {r_['stop_rate']['p50']:.3f}  ctr {r_['ctr']['p50']:.4f}  buy_rate {r_['buy_rate']['p50']:.4f}  message_rate {r_['message_rate']['p50']:.4f}  engagement {r_['engagement_rate']['p50']:.4f}"
        )
        print(f"  blockers: {a['blockers']}")
        print(f"  fatigue stop rate by exposure: {a['fatigue'].get('stop_rate_by_exposure')}")
    print("\nevidence:")
    for e in results["evidence"]:
        print(f"  {e['id']:>4} [{e['type']}] {e['statement']}")


def bench(agents: int = 20000) -> None:
    sample = load_sample(Path(__file__).resolve().parent.parent / "samples" / "sample_test.json")
    cfg = config_from_sample(sample, runs=1, agents=agents)
    ad = AdFeatures.from_dict(sample.get("ad_features", {}))
    sel = cfg.test.platforms[0]
    pop, table = build_population_and_archetypes(cfg, sel.code, 0)
    priors = priors_for_all_scenarios(table, ad, cfg, sel.code)
    from engine.simulation.runtime.montecarlo import simulate_run

    times = []
    for i in range(5):
        t0 = time.perf_counter()
        simulate_run(
            pop,
            ad,
            priors[cfg.scenarios[0].code],
            cfg,
            sel.code,
            cfg.scenarios[0],
            seed=1000 + i,
            budget_share=sel.budget_share,
        )
        times.append(time.perf_counter() - t0)
    print(
        f"{agents} agents, {int((cfg.test.schedule.get('days', 3)) * 24)} ticks: "
        + ", ".join(f"{t * 1000:.0f} ms" for t in times)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engine.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="run the engine on a sample test JSON")
    run_p.add_argument("sample")
    run_p.add_argument("--runs", type=int, default=None)
    run_p.add_argument("--agents", type=int, default=None)
    run_p.add_argument("--json", dest="json_out", default=None, help="write full results to this file")
    run_p.add_argument("--quiet", action="store_true")
    bench_p = sub.add_parser("bench", help="time single runs")
    bench_p.add_argument("--agents", type=int, default=20000)
    args = parser.parse_args(argv)
    if args.cmd == "bench":
        bench(args.agents)
        return 0
    sample = load_sample(args.sample)
    results = run_sample(sample, runs=args.runs, agents=args.agents, verbose=not args.quiet)
    print_summary(results, sample["test"].get("goal", "sales"))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, default=str)
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
