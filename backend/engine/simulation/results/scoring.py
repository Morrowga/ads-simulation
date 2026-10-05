"""Score formula: goal-dependent weights over normalised metrics (Backend document 8.6)."""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.simulation.types import GOAL_RATE

DEFAULT_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "sales": {"stop_rate": 0.20, "ctr": 0.25, "goal_rate": 0.40, "sentiment": 0.15},
    "messages": {"stop_rate": 0.20, "ctr": 0.15, "goal_rate": 0.45, "sentiment": 0.20},
    "traffic": {"stop_rate": 0.25, "goal_rate": 0.55, "sentiment": 0.20},
    "awareness": {"stop_rate": 0.50, "reach_rate": 0.30, "sentiment": 0.20},
    "engagement": {"stop_rate": 0.20, "goal_rate": 0.55, "sentiment": 0.25},
}

BENCH_KEY = {
    "stop_rate": "stop_rate",
    "ctr": "ctr",
    "reach_rate": "reach_rate",
    "sentiment": "sentiment",
}


def norm(x: float, bench: float) -> float:
    """1 - 2^(-x/benchmark): exactly 0.5 on benchmark, 0.75 at 2x, 0.875 at 3x, never clips."""
    if bench <= 0:
        return float(np.clip(x, 0.0, 1.0))
    return float(1.0 - 2.0 ** (-max(x, 0.0) / bench))


def score_run(
    metrics: dict[str, Any],
    goal: str,
    benchmarks: dict[str, float],
    weights_by_goal: dict[str, dict[str, float]] | None,
) -> float:
    weights = (
        (weights_by_goal or {}).get(goal) or DEFAULT_SCORE_WEIGHTS.get(goal) or DEFAULT_SCORE_WEIGHTS["sales"]
    )
    rates = metrics.get("rates", {})
    goal_rate_key = GOAL_RATE.get(goal, "ctr")
    values = {
        "stop_rate": float(rates.get("stop_rate", 0.0)),
        "ctr": float(rates.get("ctr", 0.0)),
        "goal_rate": float(rates.get(goal_rate_key, 0.0)),
        "reach_rate": float(rates.get("reach_rate", 0.0)),
        "sentiment": float(metrics.get("sentiment", 0.0)),
    }
    bench = {
        "stop_rate": benchmarks.get("stop_rate", 0.12),
        "ctr": benchmarks.get("ctr", 0.01),
        "goal_rate": benchmarks.get(goal_rate_key, benchmarks.get("ctr", 0.01)),
        "reach_rate": 0.5 if goal == "awareness" else 0.25,
        "sentiment": None,
    }
    total = 0.0
    wsum = 0.0
    for key, wt in weights.items():
        if key not in values:
            continue
        if key == "sentiment":
            comp = float(np.clip((values[key] + 1.0) / 2.0, 0.0, 1.0))
        else:
            comp = norm(values[key], float(bench[key] or 0.0))
        total += float(wt) * comp
        wsum += float(wt)
    if wsum <= 0:
        return 0.0
    return round(100.0 * total / wsum, 1)


def score_components(
    metrics: dict[str, Any],
    goal: str,
    benchmarks: dict[str, float],
    weights_by_goal: dict[str, dict[str, float]] | None,
) -> list[dict[str, Any]]:
    weights = (
        (weights_by_goal or {}).get(goal) or DEFAULT_SCORE_WEIGHTS.get(goal) or DEFAULT_SCORE_WEIGHTS["sales"]
    )
    rates = metrics.get("rates", {})
    goal_rate_key = GOAL_RATE.get(goal, "ctr")
    out = []
    for key, wt in weights.items():
        if key == "sentiment":
            value = float(metrics.get("sentiment", 0.0))
            bench = None
            comp = (value + 1.0) / 2.0
        elif key == "goal_rate":
            value = float(rates.get(goal_rate_key, 0.0))
            bench = float(benchmarks.get(goal_rate_key, benchmarks.get("ctr", 0.01)))
            comp = norm(value, bench)
        elif key == "reach_rate":
            value = float(rates.get("reach_rate", 0.0))
            bench = 0.5 if goal == "awareness" else 0.25
            comp = norm(value, bench)
        else:
            value = float(rates.get(key, 0.0))
            bench = float(benchmarks.get(key, 0.0))
            comp = norm(value, bench)
        out.append(
            {
                "component": key,
                "metric": goal_rate_key if key == "goal_rate" else key,
                "value": round(value, 5),
                "benchmark": bench,
                "normalised": round(float(comp), 4),
                "weight": float(wt),
            }
        )
    return out
