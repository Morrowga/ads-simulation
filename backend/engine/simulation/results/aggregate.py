"""Aggregate Monte Carlo runs: P10/P50/P90/mean per metric, funnel, segments, timing, stopping rule."""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.simulation.types import GOAL_METRIC, GOAL_RATE

COUNT_KEYS = (
    "seen",
    "impressions",
    "stopped",
    "reacted",
    "commented",
    "shared",
    "saved",
    "engagements",
    "clicked",
    "messaged",
    "bought",
    "saw_offer",
    "via_share",
    "followers_seen",
    "non_followers_seen",
)
RATE_KEYS = (
    "reach_rate",
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
    "frequency",
    "offer_seen_rate",
)


def pct(values: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return {"p10": 0.0, "p50": 0.0, "p90": 0.0, "mean": 0.0}
    return {
        "p10": float(np.percentile(arr, 10)),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "mean": float(arr.mean()),
    }


def _round(d: dict[str, float], nd: int) -> dict[str, float]:
    return {k: round(v, nd) for k, v in d.items()}


def aggregate_runs(runs: list[dict[str, Any]], goal: str) -> dict[str, Any]:
    """Aggregate a list of per-run metric dicts (same platform/audience) across scenarios."""
    if not runs:
        return {"runs": 0}
    counts = {k: _round(pct([r["counts"].get(k, 0) for r in runs]), 1) for k in COUNT_KEYS}
    rates = {k: _round(pct([r["rates"].get(k, 0.0) for r in runs]), 5) for k in RATE_KEYS}
    reference_rates: dict[str, float] = {}
    for k in RATE_KEYS:
        vals = []
        for r in runs:
            ref = r.get("reference") or {}
            ref = ref.get("rates", ref) if isinstance(ref, dict) else {}
            v = ref.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(float(v))
        if vals:
            reference_rates[k] = round(float(np.median(vals)), 5)
    goal_metric = GOAL_METRIC.get(goal, "clicks")
    goal_rate_key = GOAL_RATE.get(goal, "ctr")
    goal_values = [r.get("goal_value", 0) for r in runs]
    scores = [r.get("score", 0.0) for r in runs if r.get("score") is not None]
    sentiment = pct([r.get("sentiment", 0.0) for r in runs])
    population = int(runs[0]["counts"].get("population", 0))
    scale = float(runs[0].get("scale", 1.0))
    # funnel from medians
    funnel = {
        k: int(round(counts[k]["p50"]))
        for k in (
            "seen",
            "stopped",
            "reacted",
            "commented",
            "shared",
            "saved",
            "clicked",
            "messaged",
            "bought",
        )
    }
    funnel["skipped"] = max(funnel["seen"] - funnel["stopped"], 0)
    funnel["population"] = population
    funnel["estimated_people"] = {k: int(round(v * scale)) for k, v in funnel.items() if k != "population"}
    # segments: mean of rates across runs
    segments = _aggregate_segments(runs)
    # blockers
    blocker_totals: dict[str, float] = {}
    for r in runs:
        for k, v in r.get("blockers", {}).items():
            blocker_totals[k] = blocker_totals.get(k, 0.0) + v
    bsum = sum(blocker_totals.values())
    blockers = {
        k: {"count": round(v / len(runs), 1), "share": round(v / bsum, 4) if bsum else 0.0}
        for k, v in blocker_totals.items()
    }
    # comment topics
    topic_totals: dict[str, float] = {}
    for r in runs:
        for k, v in r.get("comment_topics", {}).items():
            topic_totals[k] = topic_totals.get(k, 0.0) + v
    tsum = sum(topic_totals.values())
    comment_topics = {
        k: {"count": round(v / len(runs), 1), "share": round(v / tsum, 4) if tsum else 0.0}
        for k, v in topic_totals.items()
    }
    # dropoff / fatigue / taste means
    dropoff = _mean_dict([r.get("dropoff", {}) for r in runs])
    fatigue = _mean_dict([r.get("fatigue", {}) for r in runs])
    taste = _mean_dict([r.get("taste", {}) for r in runs if r.get("taste")])
    # timing curves (mean per tick)
    timing = _aggregate_timing([r.get("timing", {}) for r in runs])
    # per scenario medians of the goal metric
    by_scenario: dict[str, list[float]] = {}
    for r in runs:
        by_scenario.setdefault(r.get("scenario", "normal"), []).append(float(r.get("goal_value", 0)))
    scenario_summary = {k: _round(pct(v), 1) for k, v in by_scenario.items()}
    return {
        "runs": len(runs),
        "population": population,
        "scale": scale,
        "goal": goal,
        "goal_metric": goal_metric,
        "goal_rate_key": goal_rate_key,
        "goal_value": _round(pct(goal_values), 1),
        "goal_rate": rates.get(goal_rate_key, {}),
        "score": _round(pct(scores), 1) if scores else None,
        "sentiment": _round(sentiment, 4),
        "counts": counts,
        "rates": rates,
        "reference_rates": reference_rates,
        "funnel": funnel,
        "segments": segments,
        "blockers": blockers,
        "comment_topics": comment_topics,
        "dropoff": dropoff,
        "fatigue": fatigue,
        "taste": taste,
        "timing": timing,
        "scenarios": scenario_summary,
    }


def _mean_dict(dicts: list[dict[str, Any]]) -> dict[str, Any]:
    if not dicts:
        return {}
    out: dict[str, Any] = {}
    keys = set()
    for d in dicts:
        keys |= set(d.keys())
    for k in keys:
        vals = [d.get(k) for d in dicts if d.get(k) is not None]
        if not vals:
            out[k] = None
            continue
        first = vals[0]
        if (
            isinstance(first, list)
            and first
            and not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in first)
        ):
            out[k] = first
        elif isinstance(first, list):
            length = max(len(v) for v in vals)
            acc = np.zeros(length)
            cnt = np.zeros(length)
            for v in vals:
                arr = np.asarray(v, dtype=np.float64)
                acc[: arr.size] += arr
                cnt[: arr.size] += 1
            out[k] = [round(float(a / c), 5) if c else 0.0 for a, c in zip(acc, cnt, strict=False)]
        elif isinstance(first, (int, float)) and not isinstance(first, bool):
            out[k] = round(float(np.mean([float(v) for v in vals])), 5)
        else:
            out[k] = first
    return out


def _aggregate_segments(runs: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    seg_keys = runs[0].get("segments", {}).keys()
    for sk in seg_keys:
        labels = runs[0]["segments"][sk].keys()
        out[sk] = {}
        for label in labels:
            rows = [r["segments"][sk].get(label, {}) for r in runs if sk in r.get("segments", {})]
            merged: dict[str, Any] = {}
            for field in rows[0].keys():
                vals = [float(row.get(field, 0)) for row in rows]
                merged[field] = round(float(np.mean(vals)), 5 if field.endswith("_rate") else 1)
            out[sk][label] = merged
    return out


def _aggregate_timing(timings: list[dict[str, Any]]) -> dict[str, Any]:
    if not timings:
        return {}
    out: dict[str, Any] = {"ticks": int(timings[0].get("ticks", 0))}
    for key in ("hourly_seen", "hourly_stops", "hourly_clicks", "hourly_engagements", "hourly_goal"):
        arrs = [np.asarray(t.get(key, []), dtype=np.float64) for t in timings]
        length = max((a.size for a in arrs), default=0)
        if length == 0:
            out[key] = []
            continue
        acc = np.zeros(length)
        for a in arrs:
            acc[: a.size] += a
        out[key] = [round(float(x / len(arrs)), 2) for x in acc]
    if out.get("hourly_stops"):
        out["peak_tick"] = int(np.argmax(out["hourly_stops"]))
        seen = np.asarray(out["hourly_seen"])
        total = seen.sum() or 1.0
        out["first_24h_reach_share"] = round(float(seen[:24].sum() / total), 4)
        out["last_24h_reach_share"] = round(float(seen[-24:].sum() / total), 4) if seen.size >= 48 else None
        # reach by day
        days = int(np.ceil(seen.size / 24))
        out["daily_reach"] = [int(round(seen[d * 24 : (d + 1) * 24].sum())) for d in range(days)]
        out["hour_of_day_stops"] = _hour_profile(out["hourly_stops"], timings)
    return out


def _hour_profile(hourly: list[float], timings: list[dict[str, Any]]) -> list[float]:
    # timings do not carry the start hour; the pipeline assigns it, so profile by tick modulo 24
    prof = np.zeros(24)
    for i, v in enumerate(hourly):
        prof[i % 24] += v
    return [round(float(x), 2) for x in prof]


def goal_estimate(runs: list[dict[str, Any]]) -> float:
    if not runs:
        return 0.0
    return float(np.median([r.get("goal_value", 0) for r in runs]))


def relative_change(runs: list[dict[str, Any]], last_n: int = 10) -> float:
    """Relative change of the median goal metric when the last `last_n` runs are added."""
    if len(runs) <= last_n:
        return 1.0
    before = goal_estimate(runs[:-last_n])
    after = goal_estimate(runs)
    if before == 0 and after == 0:
        return 0.0
    return abs(after - before) / max(abs(before), 1.0)


def should_stop(runs: list[dict[str, Any]], min_runs: int, threshold: float = 0.05, last_n: int = 10) -> bool:
    return len(runs) >= min_runs and relative_change(runs, last_n) < threshold


def confidence_label(n_runs: int, min_runs: int, target: int) -> str:
    if n_runs >= target or (n_runs >= min_runs):
        return "high" if n_runs >= target * 0.8 else "medium"
    if n_runs >= min_runs // 2:
        return "building"
    return "low"


def run_batch_estimate(runs: list[dict[str, Any]], goal: str) -> dict[str, Any]:
    """Compact estimate published with every run batch."""
    if not runs:
        return {}
    goal_rate_key = GOAL_RATE.get(goal, "ctr")
    return {
        "score": _round(pct([r.get("score", 0.0) for r in runs]), 1),
        "goal_value": _round(pct([r.get("goal_value", 0) for r in runs]), 1),
        goal_rate_key: _round(pct([r["rates"].get(goal_rate_key, 0.0) for r in runs]), 5),
        "ctr": _round(pct([r["rates"].get("ctr", 0.0) for r in runs]), 5),
        "stop_rate": _round(pct([r["rates"].get("stop_rate", 0.0) for r in runs]), 5),
    }


def combine_platforms(aggregates: dict[str, dict[str, Any]], shares: dict[str, float]) -> dict[str, Any]:
    """Overall numbers across platforms: counts add up, rates are reach-weighted."""
    if not aggregates:
        return {}
    total_seen = sum(a["counts"]["seen"]["p50"] for a in aggregates.values()) or 1.0
    counts = {}
    for k in COUNT_KEYS:
        counts[k] = {
            q: round(sum(a["counts"][k][q] for a in aggregates.values()), 1)
            for q in ("p10", "p50", "p90", "mean")
        }
    rates = {}
    for k in RATE_KEYS:
        rates[k] = {
            q: round(
                sum(a["rates"][k][q] * a["counts"]["seen"]["p50"] for a in aggregates.values()) / total_seen,
                5,
            )
            for q in ("p10", "p50", "p90", "mean")
        }
    goal_value = {
        q: round(sum(a["goal_value"][q] for a in aggregates.values()), 1)
        for q in ("p10", "p50", "p90", "mean")
    }
    scores = [a["score"] for a in aggregates.values() if a.get("score")]
    score = None
    if scores:
        score = {
            q: round(
                sum(
                    s[q] * sh for s, sh in zip(scores, [shares.get(k, 1.0) for k in aggregates], strict=False)
                )
                / max(sum(shares.get(k, 1.0) for k in aggregates), 1e-9),
                1,
            )
            for q in ("p10", "p50", "p90", "mean")
        }
    sentiment = {
        q: round(
            sum(a["sentiment"][q] * a["counts"]["seen"]["p50"] for a in aggregates.values()) / total_seen, 4
        )
        for q in ("p10", "p50", "p90", "mean")
    }
    return {
        "counts": counts,
        "rates": rates,
        "goal_value": goal_value,
        "score": score,
        "sentiment": sentiment,
    }
