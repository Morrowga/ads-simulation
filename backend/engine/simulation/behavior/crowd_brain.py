"""Crowd brain v1: transparent logistic model of every decision an exposed agent makes.

Inputs: the archetype's LLM reaction (priors), the agent's traits and profile columns,
the ad features, the platform and the scenario context. Weights come from the
published weight set (data/behavior_weights.yaml at seed time).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from engine.simulation.types import BLOCKERS, BRAND_REL, AdFeatures, ExposureResult, Population, ReactionPriors, Weights

DEFAULT_BEHAVIOR_WEIGHTS: dict[str, float] = {
    "b0_stop": -3.2,
    "w_hook": 1.8,
    "w_patience_impact": 0.6,
    "w_brand": 0.9,
    "w_taste": 0.8,
    "w_prior": 1.6,
    "w_int": 0.7,
    "w_fatigue": 0.45,
    "w_mood": 0.4,
    "w_hour": 0.3,
    "w_caption": 0.5,
    "w_sponsored": 0.8,
    "w_sound": 0.4,
    "w_visual": 0.6,
    "w_tone": 0.4,
    "w_clarity_stop": 1.0,
    "b0_react": -1.9,
    "w_react_sent": 1.6,
    "w_react_social": 0.8,
    "w_react_prior": 0.8,
    "b0_comment": -5.0,
    "w_comment_social": 1.5,
    "w_comment_sent_abs": 0.8,
    "w_comment_anger": 0.6,
    "w_comment_prior": 1.2,
    "b0_share": -4.8,
    "w_share_social": 1.6,
    "w_share_sent": 1.0,
    "w_share_prior": 1.0,
    "b0_save": -4.4,
    "w_save_openness": 0.8,
    "w_save_sent": 0.6,
    "b0_click": -3.9,
    "w_click_offer": 1.2,
    "w_click_prior": 1.4,
    "w_click_cta": 0.6,
    "w_click_impulse": 0.8,
    "w_click_brand": 0.6,
    "w_click_competition": 0.5,
    "w_click_caption": 0.5,
    "w_click_clarity": 2.0,
    "b0_message": -5.4,
    "w_message_cta": 1.8,
    "w_message_social": 0.9,
    "w_message_prior": 1.2,
    "b0_buy": -4.4,
    "w_buy_price": 1.4,
    "w_buy_trust": 1.2,
    "w_buy_impulse": 0.9,
    "w_buy_brand": 0.9,
    "w_buy_boost": 1.0,
    "w_buy_discount": 0.8,
    "w_buy_prior": 1.0,
    "w_buy_blocker": 0.8,
    "w_buy_clarity": 1.5,
    "brand_effect_unaware": -0.35,
    "brand_effect_aware_not_tried": 0.0,
    "brand_effect_tried_liked": 0.4,
    "brand_effect_tried_disliked": -0.6,
    "brand_effect_regular": 0.8,
    "watch_patience": 0.6,
    "watch_attention": 0.5,
    "image_dwell_s": 2.5,
}


@dataclass
class StepContext:
    hour_activity: float  # 0-1 activity of this hour
    mood: float
    competition: float
    buy_boost: float
    discount_norm: float
    sponsored: bool
    sound_on: bool
    sound_reliance: float
    trust: float  # 0-1 trust score of the ad's visible signals in this market
    tone_fit: float
    comprehension_penalty: float
    cta: str
    fatigue_rate: float
    sponsored_skepticism: float
    exposures: np.ndarray  # exposures before this one, for the exposed agents (int)
    caption_visibility: float = 0.8
    bias_stop: float = 0.0
    bias_click: float = 0.0
    bias_message: float = 0.0
    bias_buy: float = 0.0
    bias_react: float = 0.0


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def brand_effect_vector(w: Weights) -> np.ndarray:
    return np.array(
        [w.b(f"brand_effect_{k}", DEFAULT_BEHAVIOR_WEIGHTS[f"brand_effect_{k}"]) for k in BRAND_REL],
        dtype=np.float32,
    )


def taste_match(pop: Population, idx: np.ndarray, ad: AdFeatures) -> np.ndarray:
    """-1..1: how well the ad's taste profile fits each agent's taste columns."""
    if not pop.taste_names or not ad.taste_profile:
        return np.zeros(idx.shape[0], dtype=np.float32)
    cols = [
        (j, float(ad.taste_profile[nm])) for j, nm in enumerate(pop.taste_names) if nm in ad.taste_profile
    ]
    if not cols:
        return np.zeros(idx.shape[0], dtype=np.float32)
    acc = np.zeros(idx.shape[0], dtype=np.float32)
    for j, target in cols:
        acc += 1.0 - 2.0 * np.abs(pop.taste[idx, j] - target)
    return (acc / len(cols)).astype(np.float32)


def interest_match(pop: Population, idx: np.ndarray, ad: AdFeatures) -> np.ndarray:
    tags = [t for t in ad.interest_tags if t in pop.interest_names] or [
        t for t in (ad.category,) if t in pop.interest_names
    ]
    if not tags:
        return np.full(idx.shape[0], 0.1, dtype=np.float32)
    cols = [pop.interest_names.index(t) for t in tags]
    return np.clip(pop.interests[idx][:, cols].sum(axis=1) * 3.0, 0.0, 1.0).astype(np.float32)


def can_read(pop: Population, idx: np.ndarray, lang: str | None) -> np.ndarray:
    if not lang or lang not in pop.language_codes:
        # unknown language code: assume the caption language matches the country's main language
        return np.ones(idx.shape[0], dtype=bool)
    return pop.reading_langs[idx, pop.language_codes.index(lang)]


def w_(w: Weights, key: str) -> float:
    return w.b(key, DEFAULT_BEHAVIOR_WEIGHTS.get(key, 0.0))


def exposure_step(
    pop: Population,
    idx: np.ndarray,
    ad: AdFeatures,
    priors: ReactionPriors,
    ctx: StepContext,
    w: Weights,
    rng: np.random.Generator,
) -> ExposureResult:
    m = idx.shape[0]
    if m == 0:
        empty_b = np.zeros(0, dtype=bool)
        return ExposureResult(
            idx,
            empty_b,
            np.zeros(0, np.float32),
            empty_b,
            empty_b,
            empty_b,
            empty_b,
            empty_b,
            empty_b,
            empty_b,
            empty_b,
            np.full(0, -1, np.int8),
        )
    tr = pop.traits[idx]
    patience, impuls, skept, anger, openness, price_sens, social, loyalty = (tr[:, i] for i in range(8))
    a = pop.archetype[idx]
    prior_att = priors.attention[a]
    prior_sent = priors.sentiment[a]
    prior_action = priors.action[a]  # (m, len(ACTIONS))
    brand = brand_effect_vector(w)[pop.brand_rel[idx]]
    taste = taste_match(pop, idx, ad)
    interest = interest_match(pop, idx, ad)
    reads = can_read(pop, idx, ad.caption_language)
    comp = np.where(reads, 1.0, ctx.comprehension_penalty).astype(np.float32)
    caption = ad.caption_strength * ctx.caption_visibility * comp
    exposures = ctx.exposures.astype(np.float32)
    sponsored_pen = (w_(w, "w_sponsored") * ctx.sponsored_skepticism * skept) if ctx.sponsored else 0.0
    sound_term = -w_(w, "w_sound") * ctx.sound_reliance if not ctx.sound_on else 0.0
    clarity_gap = min(0.0, float(ad.clarity) - 0.6)  # 0 when clear enough, negative when confusing

    # --- attention: will the agent stop scrolling? ----------------------------
    z_stop = (
        w_(w, "b0_stop")
        + w_(w, "w_hook") * ad.attention_pull * (1.0 - w_(w, "w_patience_impact") * (1.0 - patience))
        + w_(w, "w_brand") * brand
        + w_(w, "w_taste") * taste
        + w_(w, "w_prior") * (prior_att - 0.5) * 2.0
        + w_(w, "w_int") * interest
        - w_(w, "w_fatigue") * ctx.fatigue_rate * 2.0 * np.power(exposures, 1.3)
        + w_(w, "w_mood") * ctx.mood
        + w_(w, "w_hour") * (ctx.hour_activity - 0.5)
        + w_(w, "w_caption") * caption
        + w_(w, "w_visual") * (ad.visual_quality - 0.5)
        + w_(w, "w_tone") * ctx.tone_fit
        + w_(w, "w_clarity_stop") * clarity_gap
        - sponsored_pen
        + sound_term
        + ctx.bias_stop
    )
    stop = rng.random(m) < sigmoid(z_stop)

    # --- watch time and whether the offer was seen ----------------------------
    if ad.is_video:
        frac = np.clip(
            w_(w, "watch_patience") * patience
            + w_(w, "watch_attention") * prior_att
            + rng.normal(0.0, 0.12, m)
            - 0.15,
            0.03,
            1.0,
        )
        watch_s = np.where(stop, ad.duration_s * frac, np.minimum(1.0, ad.duration_s * 0.15)).astype(
            np.float32
        )
    else:
        dwell = w_(w, "image_dwell_s") * (0.5 + patience) * (0.6 + prior_att)
        watch_s = np.where(stop, dwell, 0.4).astype(np.float32)
    if ad.offer_visible_at_s is None:
        saw_offer = stop.copy()
    else:
        saw_offer = stop & (watch_s >= float(ad.offer_visible_at_s))

    # --- engagement -------------------------------------------------------------
    z_react = (
        w_(w, "b0_react")
        + w_(w, "w_react_sent") * prior_sent
        + w_(w, "w_react_social") * social
        + w_(w, "w_react_prior") * prior_action[:, 2]
        + 0.4 * brand
        + 0.3 * ctx.mood
        + ctx.bias_react
    )
    react = stop & (rng.random(m) < sigmoid(z_react))
    z_comment = (
        w_(w, "b0_comment")
        + w_(w, "w_comment_social") * social
        + w_(w, "w_comment_sent_abs") * np.abs(prior_sent)
        + w_(w, "w_comment_anger") * anger * (prior_sent < 0)
        + w_(w, "w_comment_prior") * prior_action[:, 3]
        + 0.3 * caption
    )
    comment = stop & (rng.random(m) < sigmoid(z_comment))
    z_share = (
        w_(w, "b0_share")
        + w_(w, "w_share_social") * social
        + w_(w, "w_share_sent") * prior_sent
        + w_(w, "w_share_prior") * prior_action[:, 7]
        + 0.5 * brand
    )
    share = stop & (rng.random(m) < sigmoid(z_share))
    z_save = (
        w_(w, "b0_save")
        + w_(w, "w_save_openness") * openness
        + w_(w, "w_save_sent") * prior_sent
        + 0.3 * saw_offer
    )
    save = stop & (rng.random(m) < sigmoid(z_save))

    # --- click / message / buy -------------------------------------------------
    cta_click = (
        1.0 if ctx.cta in ("shop_now", "order_now", "learn_more", "get_offer", "sign_up", "book_now") else 0.3
    )
    z_click = (
        w_(w, "b0_click")
        + w_(w, "w_click_offer") * saw_offer
        + w_(w, "w_click_prior") * (prior_action[:, 4] + prior_action[:, 6] + 0.5 * prior_action[:, 5])
        + w_(w, "w_click_cta") * cta_click
        + w_(w, "w_click_impulse") * impuls
        + w_(w, "w_click_brand") * brand
        - w_(w, "w_click_competition") * (ctx.competition - 1.0)
        + w_(w, "w_click_caption") * caption
        + w_(w, "w_click_clarity") * clarity_gap
        + 0.5 * prior_sent
        + 0.3 * taste
        + ctx.bias_click
    )
    click = stop & (rng.random(m) < sigmoid(z_click))
    cta_msg = 1.0 if ctx.cta == "send_message" else 0.0
    z_message = (
        w_(w, "b0_message")
        + w_(w, "w_message_cta") * cta_msg
        + w_(w, "w_message_social") * social
        + w_(w, "w_message_prior") * prior_action[:, 5]
        + 0.5 * saw_offer
        + 0.4 * prior_sent
        + 0.3 * brand
        + ctx.bias_message
    )
    message = stop & (rng.random(m) < sigmoid(z_message))

    price_term = (1.0 - price_sens * ad.price_level) if ad.price_shown else (0.5 - 0.3 * price_sens)
    blocker_w = priors.blockers[a]  # (m, len(BLOCKERS))
    blocker_pressure = blocker_w[:, :5].sum(axis=1)  # everything except "none"
    z_buy = (
        w_(w, "b0_buy")
        + w_(w, "w_buy_price") * price_term
        + w_(w, "w_buy_trust") * (ctx.trust - 0.5) * (0.5 + skept)
        + w_(w, "w_buy_impulse") * impuls
        + w_(w, "w_buy_brand") * brand
        + w_(w, "w_buy_boost") * ctx.buy_boost
        + w_(w, "w_buy_discount") * (ad.discount_pct / 30.0) * price_sens * ctx.discount_norm
        + w_(w, "w_buy_prior") * prior_action[:, 6]
        + w_(w, "w_buy_clarity") * clarity_gap
        - w_(w, "w_buy_blocker") * blocker_pressure
        + 0.3 * loyalty * (brand > 0)
        + ctx.bias_buy
    )
    buy = click & saw_offer & (rng.random(m) < sigmoid(z_buy))

    # --- purchase blocker for clickers who did not buy ------------------------
    r_block = rng.random(m)  # always drawn, so the random stream does not depend on who bought
    blocker = np.full(m, -1, dtype=np.int8)
    nb = click & ~buy
    if nb.any():
        base = blocker_w[nb][:, :5] + 0.15  # (n, 5) price shipping size trust relevance
        base[:, 0] += price_sens[nb] * 0.8 + (0.4 if ad.price_shown and ad.price_level > 0.6 else 0.0)
        base[:, 3] += skept[nb] * 0.7 * (1.0 - ctx.trust)
        base[:, 4] += np.clip(-taste[nb], 0.0, 1.0) * 0.8 + (1.0 - interest[nb]) * 0.3
        base[:, 1] += 0.2 if "shipping" in ad.interest_tags or "delivery" in ad.interest_tags else 0.0
        base[:, 2] += 0.2 if ad.category in ("fashion", "beauty") else 0.0
        probs = base / base.sum(axis=1, keepdims=True)
        cum = np.cumsum(probs, axis=1)
        r = r_block[nb][:, None]
        choice = (r > cum).sum(axis=1)
        blocker[nb] = np.minimum(choice, 4).astype(np.int8)
    return ExposureResult(
        idx, stop, watch_s, saw_offer, react, comment, share, save, click, message, buy, blocker
    )


def blocker_name(i: int) -> str:
    return BLOCKERS[i] if 0 <= i < len(BLOCKERS) else "none"


def describe_weights(w: Weights) -> dict[str, Any]:
    return {k: w.b(k, v) for k, v in DEFAULT_BEHAVIOR_WEIGHTS.items()}
