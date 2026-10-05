"""Evidence table (facts with numbers) computed from aggregated runs, and the checks
applied to LLM-written reasons: evidence references, banned words, number verification.

Statements are written for a business owner: plain words, "X in 100" instead of rates,
"a typical ad in your market" instead of benchmarks. Never advice."""

from __future__ import annotations

import re
from typing import Any

from engine.simulation.types import BRAND_REL, FrozenConfig, ReactionPriors

BANNED_WORDS = (
    "should",
    "need to",
    "needs to",
    "change",
    "add",
    "remove",
    "try",
    "recommend",
    "consider",
    "improve",
    "must",
)

PLATFORM_NAME = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok"}

GOAL_VERB = {
    "ctr": "clicked",
    "buy_rate": "bought",
    "message_rate": "sent a message",
    "engagement_rate": "reacted or commented",
    "stop_rate": "stopped to look",
}

BLOCKER_LABEL = {
    "price": "price",
    "shipping": "delivery",
    "size": "size or quantity",
    "trust": "trust",
    "relevance": "not for me",
}

BRAND_LABEL = {
    "unaware": "never heard of you",
    "aware_not_tried": "know you but never tried",
    "tried_liked": "tried and liked",
    "tried_disliked": "tried and disliked",
    "regular": "regular customers",
}


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def _p(x: float, nd: int = 1) -> str:
    return f"{x * 100:.{nd}f}%"


def _per100(x: float) -> str:
    """0.123 -> '12 in 100'; 0.0143 -> '1.4 in 100'; 0.004 -> '0.4 in 100'."""
    v = float(x or 0.0) * 100.0
    s = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return f"{s} in 100"


def _plat(code: str) -> str:
    return PLATFORM_NAME.get(code.lower(), code.title())


_PLAIN = (
    (re.compile(r"\bvirtual agents\b"), "people"),
    (re.compile(r"\bfollower agents\b"), "followers"),
    (re.compile(r"\bAgents\b"), "People"),
    (re.compile(r"\bagents\b"), "people"),
    (re.compile(r"\s*\(P50\)"), ""),
)


def plain_language(text: str) -> str:
    for pat, repl in _PLAIN:
        text = pat.sub(repl, text)
    return text


class EvidenceBuilder:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        etype: str,
        statement: str,
        values: dict[str, Any],
        platform: str | None,
        audience_idx: int | None,
        importance: float = 0.5,
    ) -> str:
        eid = f"E{len(self.items) + 1}"
        self.items.append(
            {
                "id": eid,
                "type": etype,
                "statement": plain_language(statement),
                "values": values,
                "platform": platform,
                "audience_idx": audience_idx,
                "importance": round(importance, 3),
            }
        )
        return eid


def build_evidence(
    agg: dict[str, Any],
    priors: ReactionPriors,
    cfg: FrozenConfig,
    platform_code: str,
    audience_idx: int,
    ad: dict[str, Any],
    builder: EvidenceBuilder | None = None,
) -> list[dict[str, Any]]:
    """Evidence for one platform x audience aggregate. Statements are factual, never advice."""
    b = builder or EvidenceBuilder()
    p, a = platform_code, audience_idx
    pn = _plat(p)
    rates, counts = agg.get("rates", {}), agg.get("counts", {})
    # effective (layered) benchmarks when the aggregate carries them, else the platform's own
    # "a typical ad": the anchored reference ad's rates, falling back to the platform benchmark
    bench = {**cfg.platforms[platform_code].benchmarks, **(agg.get("reference_rates") or {})}
    seen = counts.get("seen", {}).get("p50", 0)
    stop = rates.get("stop_rate", {}).get("p50", 0.0)
    ctr = rates.get("ctr", {}).get("p50", 0.0)
    goal_rate = agg.get("goal_rate", {}).get("p50", 0.0)
    goal_rate_key = agg.get("goal_rate_key", "ctr")
    goal_verb = GOAL_VERB.get(goal_rate_key, goal_rate_key.replace("_", " "))
    post_type = cfg.test.post_type
    stop_bench = bench.get("stop_rate", 0.12)
    goal_bench = bench.get(goal_rate_key, bench.get("ctr", 0.01))

    # --- headline numbers -----------------------------------------------------
    b.add(
        "headline",
        f"On {pn}, about {int(seen)} of {agg.get('population', 0)} people in the audience saw the post. "
        f"{_per100(stop)} stopped to look (a typical ad in your market gets {_per100(stop_bench)}). "
        f"{_per100(goal_rate)} {goal_verb} (a typical ad gets {_per100(goal_bench)})",
        {
            "seen": seen,
            "stop_rate": stop,
            "stop_rate_benchmark": bench.get("stop_rate"),
            goal_rate_key: goal_rate,
            f"{goal_rate_key}_benchmark": bench.get(goal_rate_key),
            "ctr": ctr,
        },
        p,
        a,
        1.0,
    )
    gv = agg.get("goal_value", {})
    b.add(
        "goal_range",
        f"Expected {agg.get('goal_metric', 'clicks')} on {pn}: most likely {gv.get('p50', 0):.0f}, "
        f"between {gv.get('p10', 0):.0f} and {gv.get('p90', 0):.0f} depending on the day "
        f"(based on {agg.get('runs', 0)} simulated runs)",
        {
            "metric": agg.get("goal_metric"),
            **{k: gv.get(k) for k in ("p10", "p50", "p90")},
            "runs": agg.get("runs"),
        },
        p,
        a,
        0.9,
    )

    # --- drop-off moment ------------------------------------------------------
    d = agg.get("dropoff", {}) or {}
    offer_at = d.get("offer_visible_at_s")
    if offer_at is not None and d.get("impatient_seen"):
        b.add(
            "dropoff",
            f"Among people in a hurry who stopped, {_pct(d.get('impatient_left_share', 0.0))} left before the offer "
            f"showed up at {float(offer_at):.1f} seconds. People in a hurry clicked {_per100(d.get('impatient_ctr', 0.0))}, "
            f"patient people clicked {_per100(d.get('patient_ctr', 0.0))}. "
            f"On average people watched for {d.get('avg_watch_s', 0.0):.1f} seconds",
            {
                "offer_visible_at_s": offer_at,
                "impatient_left_share": d.get("impatient_left_share"),
                "impatient_ctr": d.get("impatient_ctr"),
                "patient_ctr": d.get("patient_ctr"),
                "avg_watch_s": d.get("avg_watch_s"),
                "all_left_before_offer_share": d.get("all_left_before_offer_share"),
            },
            p,
            a,
            0.8 if d.get("impatient_left_share", 0) > 0.3 else 0.4,
        )
    else:
        b.add(
            "dropoff",
            f"People who stopped looked at the ad for {d.get('avg_watch_s', 0.0):.1f} seconds on average. "
            f"People in a hurry clicked {_per100(d.get('impatient_ctr', 0.0))}, "
            f"patient people clicked {_per100(d.get('patient_ctr', 0.0))}",
            {
                "avg_watch_s": d.get("avg_watch_s"),
                "impatient_ctr": d.get("impatient_ctr"),
                "patient_ctr": d.get("patient_ctr"),
            },
            p,
            a,
            0.35,
        )

    # --- purchase blockers ----------------------------------------------------
    blockers = agg.get("blockers", {}) or {}
    if blockers and sum(v.get("count", 0) for v in blockers.values()) > 0:
        ordered = sorted(blockers.items(), key=lambda kv: -kv[1].get("share", 0))
        txt = ", ".join(f"{BLOCKER_LABEL.get(k, k.replace('_', ' '))} {_pct(v.get('share', 0))}" for k, v in ordered[:4])
        b.add(
            "blockers",
            f"Reasons people who clicked did not buy on {pn}: {txt}",
            {k: v.get("share") for k, v in ordered},
            p,
            a,
            0.75,
        )

    # --- segment contrasts ----------------------------------------------------
    seg = agg.get("segments", {}) or {}
    age = seg.get("age_band", {})
    rows = [(k, v) for k, v in age.items() if v.get("seen", 0) >= max(50, seen * 0.03)]
    if len(rows) >= 2:
        best = max(rows, key=lambda kv: kv[1].get("stopped_rate", 0))
        worst = min(rows, key=lambda kv: kv[1].get("stopped_rate", 0))
        b.add(
            "segment",
            f"By age on {pn}: people aged {best[0]} stopped most ({_per100(best[1].get('stopped_rate', 0))}), "
            f"people aged {worst[0]} stopped least ({_per100(worst[1].get('stopped_rate', 0))}); "
            f"everyone together {_per100(stop)}",
            {
                "best_age": best[0],
                "best_stop_rate": best[1].get("stopped_rate"),
                "worst_age": worst[0],
                "worst_stop_rate": worst[1].get("stopped_rate"),
                "overall_stop_rate": stop,
            },
            p,
            a,
            0.6,
        )
    gender = seg.get("gender", {})
    grows = [(k, v) for k, v in gender.items() if v.get("seen", 0) >= 50]
    if len(grows) >= 2:
        gtxt = "; ".join(
            f"{k}: {_per100(v.get('stopped_rate', 0))} stopped, {_per100(v.get('clicked_rate', 0))} clicked"
            for k, v in grows
        )
        b.add(
            "segment",
            f"By gender on {pn}: {gtxt}",
            {k: {"stop_rate": v.get("stopped_rate"), "ctr": v.get("clicked_rate")} for k, v in grows},
            p,
            a,
            0.4,
        )
    skept = seg.get("skeptical", {})
    if post_type in ("paid", "boosted") and skept.get("skeptical", {}).get("seen", 0) >= 50:
        s1 = skept["skeptical"].get("stopped_rate", 0.0)
        s0 = skept.get("not_skeptical", {}).get("stopped_rate", 0.0)
        b.add(
            "sponsored",
            f"Because the post is marked as an ad, people who distrust ads stopped {_per100(s1)}, "
            f"compared with {_per100(s0)} for everyone else, on {pn}",
            {"skeptical_stop_rate": s1, "other_stop_rate": s0},
            p,
            a,
            0.5 if s0 > 0 and (s0 - s1) / s0 > 0.15 else 0.25,
        )

    # --- brand relationship ---------------------------------------------------
    brand = seg.get("brand_relationship", {})
    if brand:
        total_seen = sum(v.get("seen", 0) for v in brand.values()) or 1.0
        parts = []
        vals = {}
        for k in BRAND_REL:
            v = brand.get(k, {})
            if v.get("seen", 0) >= 20:
                parts.append(
                    f"{BRAND_LABEL.get(k, k.replace('_', ' '))}: {_pct(v['seen'] / total_seen)} of the people reached, "
                    f"{_per100(v.get('clicked_rate', 0))} clicked"
                )
                vals[k] = {
                    "share_of_reach": round(v["seen"] / total_seen, 4),
                    "ctr": v.get("clicked_rate"),
                    "stop_rate": v.get("stopped_rate"),
                }
        if parts:
            b.add("brand_relationship", f"How well people know you, on {pn}: " + "; ".join(parts), vals, p, a, 0.7)

    # --- taste match ----------------------------------------------------------
    taste = agg.get("taste", {}) or {}
    if taste and taste.get("mismatch_share_of_seen"):
        b.add(
            "taste",
            f"People whose taste does not match the ad ({_pct(taste.get('mismatch_share_of_seen', 0))} of those reached) "
            f"stopped {_per100(taste.get('mismatch_stop_rate', 0))}, against {_per100(taste.get('match_stop_rate', 0))} "
            f"for people whose taste matches. {_pct(taste.get('mismatch_negative_share', 0))} of the mismatched people "
            f"who stopped had a negative first impression",
            {
                k: taste.get(k)
                for k in (
                    "mismatch_share_of_seen",
                    "mismatch_stop_rate",
                    "match_stop_rate",
                    "mismatch_negative_share",
                    "dimensions",
                )
            },
            p,
            a,
            0.55,
        )

    # --- timing and fatigue ---------------------------------------------------
    fat = agg.get("fatigue", {}) or {}
    srb = fat.get("stop_rate_by_exposure") or []
    if len(srb) >= 3 and srb[0] > 0:
        b.add(
            "timing",
            f"People get used to the ad on {pn}: {_per100(srb[0])} stopped the 1st time they saw it, "
            f"{_per100(srb[1])} the 2nd time, {_per100(srb[2])} the 3rd time. "
            f"On average each person saw it {fat.get('mean_frequency', 0):.1f} times",
            {
                "stop_rate_by_exposure": srb[:4],
                "mean_frequency": fat.get("mean_frequency"),
                "capped_share": fat.get("capped_share"),
            },
            p,
            a,
            0.5 if srb[0] and srb[2] / srb[0] < 0.7 else 0.3,
        )
    timing = agg.get("timing", {}) or {}
    if timing.get("daily_reach"):
        daily = timing["daily_reach"]
        b.add(
            "timing",
            f"People reached per day on {pn}: "
            + ", ".join(f"day {i + 1}: {int(v)}" for i, v in enumerate(daily))
            + f". {_pct(timing.get('first_24h_reach_share', 0))} of the reach came in the first 24 hours",
            {
                "daily_reach": daily,
                "first_24h_reach_share": timing.get("first_24h_reach_share"),
                "peak_tick": timing.get("peak_tick"),
            },
            p,
            a,
            0.45 if post_type == "organic" else 0.3,
        )

    # --- comment topics -------------------------------------------------------
    topics = agg.get("comment_topics", {}) or {}
    if topics and sum(v.get("count", 0) for v in topics.values()) > 0:
        ordered = sorted(topics.items(), key=lambda kv: -kv[1].get("share", 0))
        b.add(
            "comment_topics",
            f"What people wrote in comments on {pn}: "
            + ", ".join(
                f"{k.replace('_', ' ')} {_pct(v.get('share', 0))}" for k, v in ordered[:4] if v.get("share")
            ),
            {k: v.get("share") for k, v in ordered},
            p,
            a,
            0.5,
        )

    # --- language groups ------------------------------------------------------
    lg = seg.get("language_group", {})
    reads = seg.get("reads_caption", {})
    if lg:
        parts = [
            f"{k}: {int(v.get('seen', 0))} reached, {_per100(v.get('stopped_rate', 0))} stopped, "
            f"{int(v.get('commented', 0))} commented"
            for k, v in lg.items()
            if v.get("seen", 0) >= 20
        ]
        vals: dict[str, Any] = {
            k: {"seen": v.get("seen"), "stop_rate": v.get("stopped_rate"), "commented": v.get("commented")}
            for k, v in lg.items()
        }
        if reads.get("cannot_read", {}).get("seen", 0) >= 20:
            cr, rr = (
                reads["cannot_read"].get("stopped_rate", 0),
                reads.get("can_read", {}).get("stopped_rate", 0),
            )
            parts.append(
                f"people who cannot read the caption language ({ad.get('caption_language', 'unknown')}) "
                f"stopped {_per100(cr)}, against {_per100(rr)} for people who can"
            )
            vals["cannot_read_stop_rate"] = cr
            vals["can_read_stop_rate"] = rr
        if parts:
            b.add("language", f"By language on {pn}: " + "; ".join(parts), vals, p, a, 0.5)

    # --- organic reach (followers) -------------------------------------------
    if post_type in ("organic", "boosted"):
        followers = float(cfg.profile.get("followers") or 0)
        fs = counts.get("followers_seen", {}).get("p50", 0)
        nfs = counts.get("non_followers_seen", {}).get("p50", 0)
        vs = counts.get("via_share", {}).get("p50", 0)
        b.add(
            "organic_reach",
            f"Free reach on {pn} with {int(followers)} followers: {int(fs)} followers and {int(nfs)} other people saw it, "
            f"{int(vs)} of them through shares. "
            f"{'With under 100 followers the free audience is very small' if followers < 100 else 'Free reach depends on how many followers you have and how much the platform shows posts to them'}",
            {
                "followers": followers,
                "followers_seen": fs,
                "non_followers_seen": nfs,
                "via_share": vs,
                "reach_rate_of_followers": cfg.platforms[platform_code].organic.get(
                    "reach_rate_of_followers"
                ),
            },
            p,
            a,
            0.8 if followers < 100 else 0.5,
        )
    return b.items


def banned_word_hits(text: str) -> list[str]:
    low = f" {text.lower()} "
    hits = []
    for wd in BANNED_WORDS:
        if re.search(rf"\b{re.escape(wd)}\b", low):
            hits.append(wd)
    return hits


_NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def _numbers_in(values: Any, acc: set[float]) -> None:
    if isinstance(values, dict):
        for v in values.values():
            _numbers_in(v, acc)
    elif isinstance(values, (list, tuple)):
        for v in values:
            _numbers_in(v, acc)
    elif isinstance(values, bool):
        return
    elif isinstance(values, (int, float)):
        f = float(values)
        acc.add(round(f, 2))
        if 0.0 <= f <= 1.0:
            acc.add(round(f * 100.0, 0))
            acc.add(round(f * 100.0, 1))
        acc.add(round(f, 0))


def numbers_supported(
    statement: str, evidence: list[dict[str, Any]], evidence_ids: list[str], tolerance: float = 0.6
) -> bool:
    """Every number in the statement must appear (±tolerance) in the referenced evidence values or statements."""
    pool: set[float] = set()
    for e in evidence:
        if e["id"] in evidence_ids:
            _numbers_in(e.get("values"), pool)
            for m in _NUM_RE.finditer(e.get("statement", "")):
                pool.add(round(float(m.group(1)), 2))
    for m in _NUM_RE.finditer(statement):
        val = float(m.group(1))
        if any(abs(val - pv) <= tolerance for pv in pool):
            continue
        if val in (1.0, 2.0, 3.0, 24.0, 10.0, 50.0, 90.0, 100.0):  # ordinals, P10/P50/P90, "in 100"
            continue
        return False
    return True


def validate_reasons(
    reasons: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (accepted, rejected). A reason needs >=1 valid evidence id, no banned words, supported numbers."""
    valid_ids = {e["id"] for e in evidence}
    accepted, rejected = [], []
    for r in reasons:
        stmt = str(r.get("statement", "")).strip()
        ids = [i for i in (r.get("evidence_ids") or []) if i in valid_ids]
        problems = []
        if not stmt:
            problems.append("empty")
        if not ids:
            problems.append("no_evidence")
        hits = banned_word_hits(stmt)
        if hits:
            problems.append("banned_words:" + ",".join(hits))
        if ids and not numbers_supported(stmt, evidence, ids):
            problems.append("numbers_not_in_evidence")
        item = {
            "section": str(r.get("section", "general")),
            "statement": stmt,
            "evidence_ids": ids,
            "confidence": float(min(1.0, max(0.0, float(r.get("confidence", 0.5))))),
        }
        if problems:
            item["problems"] = problems
            rejected.append(item)
        else:
            accepted.append(item)
    return accepted, rejected