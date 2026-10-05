"""One Monte Carlo run of a virtual campaign: hourly ticks, reach model by post type,
frequency cap and fatigue, shares through the friend graph, and per-run metrics."""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.simulation.behavior.crowd_brain import StepContext, exposure_step
from engine.simulation.config.culture import comprehension_penalty, sponsored_skepticism, tone_fit, trust_score
from engine.simulation.runtime.timeline import build_ticks
from engine.simulation.types import (
    BLOCKERS,
    BRAND_REL,
    COMMENT_TOPICS,
    FAMILIARITY,
    GENDERS,
    GOAL_METRIC,
    GOAL_RATE,
    AdFeatures,
    FrozenConfig,
    Population,
    ReactionPriors,
    ScenarioSpec,
    age_band_label,
)


def run_seed(test_id: str, platform_code: str, audience_idx: int, run_no: int) -> int:
    import hashlib

    h = hashlib.sha256(f"{test_id}|{platform_code}|{audience_idx}|{run_no}".encode()).digest()
    return int.from_bytes(h[:8], "big") % (2**63 - 1)


def _weighted_pick(
    rng: np.random.Generator, candidates: np.ndarray, weights: np.ndarray, k: int
) -> np.ndarray:
    """Pick k of the candidates without replacement, with probability roughly proportional to weights (Gumbel top-k)."""
    if k <= 0 or candidates.shape[0] == 0:
        return candidates[:0]
    if k >= candidates.shape[0]:
        return candidates
    keys = np.log(np.maximum(weights, 1e-6)) + rng.gumbel(size=candidates.shape[0])
    top = np.argpartition(-keys, k - 1)[:k]
    return candidates[top]


def simulate_run(
    pop: Population,
    ad: AdFeatures,
    priors: ReactionPriors,
    cfg: FrozenConfig,
    platform_code: str,
    scenario: ScenarioSpec,
    seed: int,
    budget_share: float = 100.0,
    bias: dict[str, float] | None = None,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    platform = cfg.platforms[platform_code]
    w = cfg.weights
    n = pop.n
    post_type = cfg.test.post_type
    ticks = build_ticks(cfg, platform, scenario, budget_share, n, pop.scale)
    freq_cap = int(platform.behavior.get("frequency_cap_per_day", 3)) * max(1, len(ticks) // 24)
    sound_on = str(platform.behavior.get("sound_default", "off")).lower() in ("on", "true", "1")
    bias = bias or {}
    ctx_static = dict(
        mood=float(scenario.mood),
        competition=float(scenario.competition),
        buy_boost=float(scenario.buy_boost),
        discount_norm=float(scenario.discount_norm),
        sponsored=post_type in ("paid", "boosted"),
        sound_on=sound_on,
        sound_reliance=float(ad.sound_reliance),
        trust=trust_score(cfg, ad.trust_signals),
        tone_fit=tone_fit(cfg, ad.emotional_tone),
        comprehension_penalty=comprehension_penalty(cfg),
        cta=str(ad.cta or "learn_more"),
        fatigue_rate=float(platform.behavior.get("fatigue_rate", 0.35)),
        sponsored_skepticism=sponsored_skepticism(cfg),
        caption_visibility=float(platform.behavior.get("caption_visibility", 0.8)),
        bias_stop=float(bias.get("stop", 0.0)),
        bias_click=float(bias.get("click", 0.0)),
        bias_message=float(bias.get("message", 0.0)),
        bias_buy=float(bias.get("buy", 0.0)),
        bias_react=float(bias.get("react", 0.0)),
    )

    # state
    exposures = np.zeros(n, dtype=np.int16)
    stopped = np.zeros(n, dtype=bool)
    reacted = np.zeros(n, dtype=bool)
    commented = np.zeros(n, dtype=bool)
    shared = np.zeros(n, dtype=bool)
    saved = np.zeros(n, dtype=bool)
    clicked = np.zeros(n, dtype=bool)
    messaged = np.zeros(n, dtype=bool)
    bought = np.zeros(n, dtype=bool)
    left_before_offer = np.zeros(n, dtype=bool)
    saw_offer_any = np.zeros(n, dtype=bool)
    blocker = np.full(n, -1, dtype=np.int8)
    first_seen_tick = np.full(n, -1, dtype=np.int32)
    via_share = np.zeros(n, dtype=bool)
    share_pending = np.zeros(n, dtype=bool)  # shared in the previous tick -> friends' feeds now
    stops_by_exposure = np.zeros(4, dtype=np.int64)  # exposure #1, #2, #3, 4+
    seen_by_exposure = np.zeros(4, dtype=np.int64)
    hourly_seen = np.zeros(len(ticks), dtype=np.int64)
    hourly_stops = np.zeros(len(ticks), dtype=np.int64)
    hourly_clicks = np.zeros(len(ticks), dtype=np.int64)
    hourly_engage = np.zeros(len(ticks), dtype=np.int64)
    hourly_goal = np.zeros(len(ticks), dtype=np.int64)
    watch_sum = 0.0
    watch_count = 0

    organic = platform.organic
    reach_rate = float(organic.get("reach_rate_of_followers", 0.06))
    share_boost = float(organic.get("share_boost", 0.3))
    ranking_w = float(organic.get("ranking_engagement_weight", 0.5))
    followers_idx = np.where(pop.is_follower)[0]
    n_followers = followers_idx.shape[0]
    prior_att_agents = priors.attention[pop.archetype]
    goal_key = GOAL_METRIC.get(cfg.test.goal, "clicks")

    for tick in ticks:
        online = (
            rng.random(n) < pop.active_hours[:, tick.hour] * min(tick.activity, 1.5)
        ) & pop.uses_platform
        eligible = online & (exposures < freq_cap)
        exposed_parts: list[np.ndarray] = []
        eng_rate_so_far = float((reacted | commented | shared | clicked).sum()) / max(
            1.0, float((exposures > 0).sum())
        )

        # --- organic / follower part -------------------------------------------
        if post_type in ("organic", "boosted") and n_followers > 0 and tick.organic_factor > 0.02:
            base = n_followers * reach_rate * tick.organic_factor * (0.5 + tick.activity) * 2.0
            base *= 1.0 + ranking_w * eng_rate_so_far * 4.0
            cand = followers_idx[eligible[followers_idx] & (exposures[followers_idx] == 0)]
            k = int(min(cand.shape[0], round(base + rng.random())))
            if k > 0:
                pick = _weighted_pick(rng, cand, 1.0 + prior_att_agents[cand], k)
                exposed_parts.append(pick)
            # ranking pushes a post with good engagement to non-followers as well
            extra = base * ranking_w * eng_rate_so_far * 6.0
            if extra >= 1.0:
                nf = np.where(eligible & ~pop.is_follower & (exposures == 0))[0]
                k2 = int(min(nf.shape[0], round(extra)))
                if k2 > 0:
                    exposed_parts.append(_weighted_pick(rng, nf, 1.0 + prior_att_agents[nf], k2))

        # --- shares from the previous tick land in friends' feeds ----------------
        if post_type in ("organic", "boosted") and share_pending.any():
            reach_vec = pop.friends @ share_pending.astype(np.float32)
            friends_hit = np.where((reach_vec > 0) & eligible & (exposures == 0))[0]
            if friends_hit.shape[0]:
                take = friends_hit[rng.random(friends_hit.shape[0]) < share_boost]
                via_share[take] = True
                exposed_parts.append(take)
        share_pending[:] = False

        # --- paid impressions ------------------------------------------------------
        if post_type in ("paid", "boosted") and tick.impressions > 0:
            already = np.zeros(n, dtype=bool)
            for p in exposed_parts:
                already[p] = True
            cand = np.where(eligible & ~already)[0]
            # platform ranking: mild preference for people likely to engage, plus repeat serving under the cap
            weights = (1.0 + ranking_w * prior_att_agents[cand]) / (1.0 + 0.6 * exposures[cand])
            pick = _weighted_pick(rng, cand, weights, tick.impressions)
            if pick.shape[0]:
                exposed_parts.append(pick)

        if not exposed_parts:
            continue
        idx = np.unique(np.concatenate(exposed_parts))
        prev_exp = exposures[idx].copy()
        ctx = StepContext(hour_activity=min(1.0, tick.activity), exposures=prev_exp, **ctx_static)
        res = exposure_step(pop, idx, ad, priors, ctx, w, rng)

        # --- update state ----------------------------------------------------------
        exposures[idx] += 1
        new = first_seen_tick[idx] < 0
        first_seen_tick[idx[new]] = tick.t
        hourly_seen[tick.t] = int(new.sum())
        bucket = np.minimum(prev_exp, 3)
        np.add.at(seen_by_exposure, bucket, 1)
        np.add.at(stops_by_exposure, bucket[res.stop], 1)
        stopped[idx[res.stop]] = True
        reacted[idx[res.react]] = True
        commented[idx[res.comment]] = True
        shared[idx[res.share]] = True
        share_pending[idx[res.share]] = True
        saved[idx[res.save]] = True
        clicked[idx[res.click]] = True
        messaged[idx[res.message]] = True
        bought[idx[res.buy]] = True
        saw_offer_any[idx[res.saw_offer]] = True
        if ad.offer_visible_at_s is not None:
            left_before_offer[idx[res.stop & ~res.saw_offer]] = True
        nb = res.blocker >= 0
        blocker[idx[nb]] = res.blocker[nb]
        hourly_stops[tick.t] = int(res.stop.sum())
        hourly_clicks[tick.t] = int(res.click.sum())
        hourly_engage[tick.t] = int((res.react | res.comment | res.share | res.save).sum())
        hourly_goal[tick.t] = int(
            {
                "buys": res.buy.sum(),
                "messages": res.message.sum(),
                "clicks": res.click.sum(),
                "noticed": res.stop.sum(),
                "engagements": (res.react | res.comment | res.share | res.save).sum(),
            }[goal_key]
        )
        if res.stop.any():
            watch_sum += float(res.watch_s[res.stop].sum())
            watch_count += int(res.stop.sum())

    return _collect_metrics(
        pop,
        ad,
        priors,
        cfg,
        platform_code,
        scenario,
        seed,
        exposures,
        stopped,
        reacted,
        commented,
        shared,
        saved,
        clicked,
        messaged,
        bought,
        left_before_offer,
        saw_offer_any,
        blocker,
        via_share,
        seen_by_exposure,
        stops_by_exposure,
        hourly_seen,
        hourly_stops,
        hourly_clicks,
        hourly_engage,
        hourly_goal,
        watch_sum / max(watch_count, 1),
        ticks_n=len(ticks),
    )


def _rate(a: float | int, b: float | int) -> float:
    return float(a) / float(b) if b else 0.0


def _segment(
    key_arr: np.ndarray, labels: list[str], seen: np.ndarray, **flags: np.ndarray
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    k = len(labels)
    seen_c = np.bincount(key_arr[seen].astype(np.int64), minlength=k)
    counts = {name: np.bincount(key_arr[arr].astype(np.int64), minlength=k) for name, arr in flags.items()}
    for i, label in enumerate(labels):
        s = int(seen_c[i])
        row: dict[str, Any] = {"seen": s}
        for name, c in counts.items():
            row[name] = int(c[i])
            row[f"{name}_rate"] = round(_rate(int(c[i]), s), 5)
        out[label] = row
    return out


def _collect_metrics(
    pop: Population,
    ad: AdFeatures,
    priors: ReactionPriors,
    cfg: FrozenConfig,
    platform_code: str,
    scenario: ScenarioSpec,
    seed: int,
    exposures: np.ndarray,
    stopped: np.ndarray,
    reacted: np.ndarray,
    commented: np.ndarray,
    shared: np.ndarray,
    saved: np.ndarray,
    clicked: np.ndarray,
    messaged: np.ndarray,
    bought: np.ndarray,
    left_before_offer: np.ndarray,
    saw_offer_any: np.ndarray,
    blocker: np.ndarray,
    via_share: np.ndarray,
    seen_by_exposure: np.ndarray,
    stops_by_exposure: np.ndarray,
    hourly_seen: np.ndarray,
    hourly_stops: np.ndarray,
    hourly_clicks: np.ndarray,
    hourly_engage: np.ndarray,
    hourly_goal: np.ndarray,
    avg_watch_s: float,
    ticks_n: int,
) -> dict[str, Any]:
    seen = exposures > 0
    n_seen = int(seen.sum())
    impressions = int(exposures.sum())
    engaged = reacted | commented | shared | saved
    counts = {
        "population": int(pop.n),
        "seen": n_seen,
        "impressions": impressions,
        "stopped": int(stopped.sum()),
        "noticed": int(stopped.sum()),
        "reacted": int(reacted.sum()),
        "commented": int(commented.sum()),
        "shared": int(shared.sum()),
        "saved": int(saved.sum()),
        "engagements": int(engaged.sum()),
        "clicked": int(clicked.sum()),
        "clicks": int(clicked.sum()),
        "messaged": int(messaged.sum()),
        "messages": int(messaged.sum()),
        "bought": int(bought.sum()),
        "buys": int(bought.sum()),
        "saw_offer": int(saw_offer_any.sum()),
        "via_share": int(via_share.sum()),
        "followers_seen": int((seen & pop.is_follower).sum()),
        "non_followers_seen": int((seen & ~pop.is_follower).sum()),
        "skipped": int(n_seen - stopped.sum()),
    }
    rates = {
        "reach_rate": round(_rate(n_seen, pop.n), 5),
        "stop_rate": round(_rate(counts["stopped"], n_seen), 5),
        "ctr": round(_rate(counts["clicked"], n_seen), 5),
        "buy_rate": round(_rate(counts["bought"], n_seen), 5),
        "cvr": round(_rate(counts["bought"], counts["clicked"]), 5),
        "message_rate": round(_rate(counts["messaged"], n_seen), 5),
        "engagement_rate": round(_rate(counts["engagements"], n_seen), 5),
        "react_rate": round(_rate(counts["reacted"], n_seen), 5),
        "comment_rate": round(_rate(counts["commented"], n_seen), 5),
        "share_rate": round(_rate(counts["shared"], n_seen), 5),
        "save_rate": round(_rate(counts["saved"], n_seen), 5),
        "frequency": round(_rate(impressions, n_seen), 3),
        "offer_seen_rate": round(_rate(counts["saw_offer"], counts["stopped"]), 5),
    }
    sent = priors.sentiment[pop.archetype]
    sentiment = float(sent[stopped].mean()) if counts["stopped"] else 0.0
    goal_metric = GOAL_METRIC.get(cfg.test.goal, "clicks")
    goal_rate_key = GOAL_RATE.get(cfg.test.goal, "ctr")
    goal_value = counts[goal_metric] if goal_metric != "noticed" else counts["stopped"]
    if cfg.test.goal == "awareness":
        goal_value = counts["stopped"]
    patience = pop.traits[:, 0]
    skept = pop.traits[:, 2]
    impatient = patience < 0.4
    reads = np.ones(pop.n, dtype=bool)
    if ad.caption_language in pop.language_codes:
        reads = pop.reading_langs[:, pop.language_codes.index(ad.caption_language)]
    tercile = np.digitize(patience, [0.35, 0.6]).astype(np.int8)
    segments = {
        "age_band": _segment(
            pop.age_band,
            [age_band_label(i) for i in range(7)],
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
            messaged=messaged,
            commented=commented,
            engaged=engaged,
        ),
        "gender": _segment(
            pop.gender,
            list(GENDERS),
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
            messaged=messaged,
            engaged=engaged,
        ),
        "brand_relationship": _segment(
            pop.brand_rel,
            list(BRAND_REL),
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
            messaged=messaged,
            commented=commented,
            engaged=engaged,
            shared=shared,
        ),
        "familiarity": _segment(
            pop.familiarity,
            list(FAMILIARITY),
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
            engaged=engaged,
        ),
        "language_group": _segment(
            pop.language_group,
            list(pop.language_group_codes),
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
            messaged=messaged,
            commented=commented,
            engaged=engaged,
        ),
        "patience": _segment(
            tercile, ["impatient", "medium", "patient"], seen, stopped=stopped, clicked=clicked, bought=bought
        ),
        "reads_caption": _segment(
            reads.astype(np.int8),
            ["cannot_read", "can_read"],
            seen,
            stopped=stopped,
            clicked=clicked,
            commented=commented,
        ),
        "skeptical": _segment(
            (skept > 0.6).astype(np.int8),
            ["not_skeptical", "skeptical"],
            seen,
            stopped=stopped,
            clicked=clicked,
            bought=bought,
        ),
        "follower": _segment(
            pop.is_follower.astype(np.int8),
            ["non_follower", "follower"],
            seen,
            stopped=stopped,
            clicked=clicked,
            engaged=engaged,
            shared=shared,
        ),
    }
    blockers = {name: int((blocker == i).sum()) for i, name in enumerate(BLOCKERS[:5])}
    blockers_total = sum(blockers.values())
    dropoff = {
        "offer_visible_at_s": ad.offer_visible_at_s,
        "impatient_seen": int((seen & impatient).sum()),
        "impatient_left_before_offer": int((left_before_offer & impatient).sum()),
        "impatient_left_share": round(
            _rate(int((left_before_offer & impatient & stopped).sum()), int((stopped & impatient).sum())), 4
        ),
        "all_left_before_offer_share": round(
            _rate(int((left_before_offer & stopped).sum()), counts["stopped"]), 4
        ),
        "avg_watch_s": round(avg_watch_s, 2),
        "impatient_ctr": round(_rate(int((clicked & impatient).sum()), int((seen & impatient).sum())), 5),
        "patient_ctr": round(_rate(int((clicked & ~impatient).sum()), int((seen & ~impatient).sum())), 5),
    }
    fatigue = {
        "seen_by_exposure": [int(x) for x in seen_by_exposure],
        "stops_by_exposure": [int(x) for x in stops_by_exposure],
        "stop_rate_by_exposure": [
            round(_rate(int(s), int(e)), 5) for s, e in zip(stops_by_exposure, seen_by_exposure, strict=False)
        ],
        "mean_frequency": rates["frequency"],
        "capped_share": round(
            _rate(
                int(
                    (
                        exposures
                        >= max(
                            1,
                            int(cfg.platforms[platform_code].behavior.get("frequency_cap_per_day", 3))
                            * max(1, ticks_n // 24),
                        )
                    ).sum()
                ),
                n_seen,
            ),
            4,
        ),
    }
    # taste
    taste_info: dict[str, Any] = {}
    if pop.taste_names and ad.taste_profile:
        from engine.simulation.behavior.crowd_brain import taste_match

        all_idx = np.arange(pop.n)
        tm = taste_match(pop, all_idx, ad)
        mismatch = tm < -0.2
        taste_info = {
            "mismatch_share_of_seen": round(_rate(int((seen & mismatch).sum()), n_seen), 4),
            "mismatch_stop_rate": round(
                _rate(int((stopped & mismatch).sum()), int((seen & mismatch).sum())), 5
            ),
            "match_stop_rate": round(
                _rate(int((stopped & ~mismatch).sum()), int((seen & ~mismatch).sum())), 5
            ),
            "mismatch_negative_share": round(
                _rate(int((stopped & mismatch & (sent < -0.1)).sum()), int((stopped & mismatch).sum())), 4
            ),
            "dimensions": list(ad.taste_profile.keys()),
        }
    # comment topics: the archetype's LLM topic when it has one, otherwise derived from the commenter's
    # price sensitivity and the archetype sentiment (same rule the mock classifier uses)
    topic_counts = dict.fromkeys(COMMENT_TOPICS, 0)
    commenters = np.where(commented)[0]
    for i in commenters:
        a = int(pop.archetype[i])
        t = priors.comment_topic[a]
        if not t:
            ps = float(pop.traits[i, 5])
            s = float(priors.sentiment[a])
            if ps > 0.62 and not ad.price_shown:
                t = "price"
            elif s > 0.3:
                t = "positive"
            elif s < -0.3:
                t = "negative"
            elif i % 2 == 0:
                t = "product_detail"
            else:
                t = "service"
        topic_counts[t] = topic_counts.get(t, 0) + 1
    # per hour timing
    peak_tick = int(np.argmax(hourly_stops)) if hourly_stops.size else 0
    timing = {
        "ticks": int(ticks_n),
        "hourly_seen": [int(x) for x in hourly_seen],
        "hourly_stops": [int(x) for x in hourly_stops],
        "hourly_clicks": [int(x) for x in hourly_clicks],
        "hourly_engagements": [int(x) for x in hourly_engage],
        "hourly_goal": [int(x) for x in hourly_goal],
        "peak_tick": peak_tick,
        "first_24h_reach_share": round(_rate(int(hourly_seen[:24].sum()), n_seen), 4),
        "last_24h_reach_share": round(_rate(int(hourly_seen[-24:].sum()), n_seen), 4)
        if ticks_n >= 48
        else None,
    }
    return {
        "platform": platform_code,
        "scenario": scenario.code,
        "seed": int(seed),
        "goal": cfg.test.goal,
        "goal_metric": goal_metric,
        "goal_value": int(goal_value),
        "goal_rate_key": goal_rate_key,
        "goal_rate": rates.get(goal_rate_key, 0.0),
        "counts": counts,
        "rates": rates,
        "sentiment": round(sentiment, 4),
        "segments": segments,
        "blockers": blockers,
        "blockers_total": blockers_total,
        "dropoff": dropoff,
        "fatigue": fatigue,
        "taste": taste_info,
        "comment_topics": topic_counts,
        "timing": timing,
        "scale": float(pop.scale),
    }
