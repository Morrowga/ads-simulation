"""Reaction priors: turn per-archetype reactions into arrays the crowd brain can use,
plus a deterministic, category-driven reaction generator (no LLM)."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from engine.simulation.types import ACTIONS, BLOCKERS, COMMENT_TOPICS, AdFeatures, ReactionPriors, ScenarioSpec

REACTION_KEYS = (
    "attention",
    "first_impression",
    "image_impressed",
    "caption_read",
    "sentiment",
    "likely_action",
    "comment",
    "comment_topic",
    "purchase_blockers",
    "reason",
)


def _stable_seed(*parts: Any) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % (2**63 - 1)


COMMENT_TEMPLATES = {
    "price": [
        "How much is this?",
        "Is there a discount if I order more than one?",
        "Price please, nothing in the caption.",
        "Looks nice but probably expensive.",
    ],
    "product_detail": [
        "Can you share more details about this?",
        "What options or sizes do you have?",
        "Where exactly is the shop?",
        "Is there more information somewhere?",
    ],
    "service": [
        "Do you deliver to my area?",
        "How long does delivery usually take?",
        "Are you open on weekends?",
        "Can I message you to order?",
    ],
    "positive": [
        "Looks great, saving this for later.",
        "Tagging my friends, we need to check this out.",
        "This is exactly what I was looking for.",
        "Love this, well done.",
    ],
    "negative": [
        "Seen this ad five times already.",
        "The photo looks edited, not convinced.",
        "Tried it once, was not worth the price.",
        "Too many ads like this lately.",
    ],
    "other": [
        "Is this the place near the station?",
        "Reminds me of home.",
        "Nice video.",
        "Where can I see more?",
    ],
}

CATEGORY_COMMENTS: dict[str, dict[str, list[str]]] = {
    "restaurant": {
        "product_detail": ["Is this spicy? I can't take too much chilli.", "What size is the portion?"],
        "service": ["Can I book a table for six?", "Open on Sundays?"],
        "positive": ["Looks amazing, saving this for the weekend.", "This is exactly what I was craving."],
    },
    "cafe_drinks": {
        "product_detail": ["Is it very sweet?", "Do you have oat milk?"],
        "service": ["Is there wifi and a place to work?", "What time do you open?"],
        "positive": ["That latte art is so nice.", "Meeting friends here this weekend."],
    },
    "fashion": {
        "product_detail": ["Do you have this in other sizes?", "Do you have this in other colours?"],
        "service": ["Can I return it if it doesn't fit?", "Is there free shipping?"],
        "positive": ["Love this style, need it.", "That colour looks so good."],
    },
    "beauty": {
        "product_detail": ["Is it safe for sensitive skin?", "What are the ingredients?"],
        "service": ["Is it registered and certified?", "Do you ship nationwide?"],
        "positive": ["My skin needs this, saving it.", "Reviews look promising."],
    },
    "online_shop": {
        "product_detail": ["What are the specs?", "Does it come with a warranty?"],
        "service": ["Is cash on delivery available?", "How many days for shipping?"],
        "positive": ["Good price, adding to my list.", "Finally something useful."],
    },
}

FIRST_IMPRESSIONS = [
    "Eye-catching, but I don't know this brand.",
    "Another ad, scrolling on.",
    "The offer looks clear and the price is visible.",
    "Looks sponsored, not sure it's real.",
    "I know this shop and I like it.",
    "Caption is in a language I don't read well.",
    "Discount catches the eye, might check it.",
    "Too much text on the image.",
]

_DEFAULT_BLOCKER_WEIGHTS = {"price": 0.3, "relevance": 0.25, "trust": 0.2, "shipping": 0.15, "size": 0.1}


def _cat(category: Any, name: str, default: Any) -> Any:
    if category is None:
        return default
    if isinstance(category, dict):
        return category.get(name, default)
    return getattr(category, name, default)


def _feature_value(name: str, ad: AdFeatures, trust_w: dict[str, float]) -> float | None:
    """An ad feature as a 0-1 number, or None when the name is unknown."""
    if name == "price_shown":
        return 1.0 if ad.price_shown else 0.0
    if name == "discount_pct":
        return min(1.0, float(ad.discount_pct) / 30.0)
    if name == "trust_signals":
        if not ad.trust_signals:
            return 0.0
        return min(1.0, sum(trust_w.get(s, 0.3) for s in ad.trust_signals) / 2.0)
    if name.startswith("taste_profile."):
        return float(ad.taste_profile.get(name.split(".", 1)[1], 0.5))
    v = getattr(ad, name, None)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(min(1.0, max(0.0, v)))
    return None


def _trait_value(name: str, archetype: dict[str, Any]) -> float:
    if name.startswith("taste."):
        return float((archetype.get("taste") or {}).get(name.split(".", 1)[1], 0.5))
    return float((archetype.get("traits") or {}).get(name, 0.5))


def _rule_effect(
    rule: dict[str, Any], ad: AdFeatures, archetype: dict[str, Any], trust_w: dict[str, float]
) -> float:
    """One activation rule (ad feature -> trait, weight) as a small signed effect, roughly -0.5..0.5."""
    feature = str(rule.get("ad_feature", ""))
    trait = str(rule.get("trait", ""))
    f = _feature_value(feature, ad, trust_w)
    if f is None or not trait:
        return 0.0
    t = _trait_value(trait, archetype)
    w = float(rule.get("weight", 0.5))
    if trait.startswith("taste."):
        return w * (0.5 - abs(f - t))  # closer taste = positive
    if trait == "patience":
        return w * (f - 0.5) * (1.0 - t)  # impatient people depend on a strong hook
    if trait == "skepticism":
        return w * (f - 0.3) * t  # skeptical people are moved by trust, and lost without it
    if trait == "price_sensitivity":
        if feature == "discount_pct":
            return w * f * (t - 0.3)
        if feature == "price_shown":
            return w * f * t * (0.6 - float(ad.price_level))
    return w * (f - 0.5) * (t - 0.5)


def heuristic_reaction(
    archetype: dict[str, Any],
    ad: AdFeatures | dict[str, Any],
    scenario: ScenarioSpec | dict[str, Any] | None,
    platform_code: str,
    post_type: str,
    seed_salt: str = "",
    category: Any = None,
) -> dict[str, Any]:
    """Deterministic reaction for an archetype (no LLM), driven by the category template when given:
    activation_rules, buying_behavior, blockers and trust_signals. Always English."""
    if isinstance(ad, dict):
        ad = AdFeatures.from_dict(ad)
    if isinstance(scenario, dict):
        scenario = ScenarioSpec.from_dict(scenario)
    scenario = scenario or ScenarioSpec("normal", "Normal week")
    rng = np.random.default_rng(
        _stable_seed(archetype.get("label"), archetype.get("idx"), platform_code, scenario.code, seed_salt)
    )
    code = str(_cat(category, "code", "") or "")
    rules = _cat(category, "activation_rules", []) or []
    buying = _cat(category, "buying_behavior", {}) or {}
    blocker_cfg = _cat(category, "blockers", []) or []
    trust_w = {
        str(t.get("code")): float(t.get("weight", 0.5))
        for t in (_cat(category, "trust_signals", []) or [])
        if t.get("code")
    }

    traits = archetype.get("traits", {})
    patience = float(traits.get("patience", 0.5))
    impuls = float(traits.get("impulsiveness", 0.5))
    skept = float(traits.get("skepticism", 0.5))
    price_sens = float(traits.get("price_sensitivity", 0.5))
    social = float(traits.get("social", 0.5))
    brand = archetype.get("brand_relationship", "unaware")
    reads = archetype.get("reads", ["en"])
    can_read = ad.caption_language in reads or not ad.caption_language
    brand_effect = {
        "unaware": -0.12,
        "aware_not_tried": 0.0,
        "tried_liked": 0.15,
        "tried_disliked": -0.25,
        "regular": 0.25,
    }.get(brand, 0.0)
    taste = archetype.get("taste", {}) or {}
    taste_match = 0.0
    if ad.taste_profile and taste:
        diffs = [abs(float(taste.get(k, 0.5)) - float(v)) for k, v in ad.taste_profile.items() if k in taste]
        if diffs:
            taste_match = 0.5 - float(np.mean(diffs))
    sponsored = post_type in ("paid", "boosted")
    rule_sum = sum(_rule_effect(r, ad, archetype, trust_w) for r in rules)

    attention = float(
        np.clip(
            0.18
            + 0.45 * ad.attention_pull
            + 0.15 * ad.visual_quality
            + brand_effect
            + 0.15 * taste_match
            + 0.20 * rule_sum
            + 0.10 * scenario.mood
            - (0.18 * skept if sponsored else 0.0)
            - (0.08 if not can_read else 0.0)
            + rng.normal(0, 0.06),
            0.02,
            0.95,
        )
    )
    sentiment = float(
        np.clip(
            0.05
            + 0.5 * taste_match
            + 0.6 * brand_effect
            + 0.2 * (ad.visual_quality - 0.5)
            + 0.25 * rule_sum
            + scenario.mood * 0.3
            + (0.1 if ad.discount_pct > 0 and price_sens > 0.5 else 0.0)
            - (0.15 * skept if sponsored else 0.0)
            + rng.normal(0, 0.12),
            -1.0,
            1.0,
        )
    )
    price_ok = (not ad.price_shown) or (ad.price_level < 0.5 + (1 - price_sens) * 0.5)

    # --- action: attention decides whether they stop, then intent / reaction / comment ---
    action = "skip" if attention < 0.28 else "pause"
    if rng.random() < attention:
        pos = max(sentiment, 0.0)
        impulse_bias = float(buying.get("impulse_share", 0.5)) - 0.5
        p_intent = float(
            np.clip(
                0.12 + 0.55 * pos + 0.3 * (impuls - 0.5) + 0.3 * impulse_bias + 0.1 * scenario.buy_boost,
                0.02,
                0.8,
            )
        )
        p_react = 0.2 + 0.4 * pos
        if rng.random() < p_intent:
            action = "click"
            if ad.cta == "send_message" and social > 0.4:
                action = "message"
            elif (
                price_ok
                and impuls > 0.5
                and (brand in ("tried_liked", "regular") or ad.discount_pct > 0)
                and rng.random() < 0.6
            ):
                action = "buy"
        elif sentiment > 0.0 and rng.random() < p_react:
            action = "react"
        elif social > 0.65 and rng.random() < 0.3:
            action = "comment"
        else:
            action = "pause"

    # --- blockers from the category's own blocker weights ---
    blockers: list[str] = []
    if action not in ("skip", "buy"):
        weights = {
            str(b.get("code")): float(b.get("weight", 0.1)) for b in blocker_cfg if b.get("code")
        } or dict(_DEFAULT_BLOCKER_WEIGHTS)
        trust_level = _feature_value("trust_signals", ad, trust_w) or 0.0
        mods = {
            "price": 0.5 + price_sens + (0.3 if ad.price_shown and ad.price_level > 0.6 else 0.0),
            "trust": 2.0 * skept * (1.0 - trust_level),
            "relevance": max(0.0, 1.0 - 2.0 * taste_match),
            "shipping": 0.6,
            "size": 0.6,
        }
        for bcode, bw in weights.items():
            if bcode in mods and rng.random() < min(0.6, bw * mods[bcode] * 0.7):
                blockers.append(bcode)
            if len(blockers) >= 2:
                break
    if not blockers:
        blockers = ["none"]

    # --- comment ---
    topic: str | None = None
    comment: str | None = None
    wants_comment = action == "comment" or (social > 0.7 and attention > 0.5 and rng.random() < 0.3)
    if wants_comment:
        if price_sens > 0.6 and not ad.price_shown:
            topic = "price"
        elif sentiment > 0.35:
            topic = "positive"
        elif sentiment < -0.3:
            topic = "negative"
        elif rng.random() < 0.5:
            topic = "product_detail"
        else:
            topic = "service"
        options = COMMENT_TEMPLATES[topic] + CATEGORY_COMMENTS.get(code, {}).get(topic, [])
        comment = options[int(rng.integers(0, len(options)))]

    reason_bits = [
        f"hook {'strong' if ad.hook_strength > 0.6 else 'weak'} for an {'impatient' if patience < 0.4 else 'patient'} viewer",
        f"brand: {brand.replace('_', ' ')}",
    ]
    if rule_sum > 0.05:
        reason_bits.append("ad matches what this group responds to")
    elif rule_sum < -0.05:
        reason_bits.append("ad misses what this group responds to")
    if sponsored and skept > 0.55:
        reason_bits.append("sponsored label lowers trust")
    if not can_read:
        reason_bits.append("caption not in a language they read")
    if ad.offer_visible_at_s and ad.offer_visible_at_s > 2.5 and patience < 0.4:
        reason_bits.append("offer appears after they would have scrolled")
    fi = FIRST_IMPRESSIONS[int(rng.integers(0, len(FIRST_IMPRESSIONS)))]
    if brand in ("tried_liked", "regular"):
        fi = "I know this shop and I like it."
    elif not can_read:
        fi = "Caption is in a language I don't read well."
    return {
        "attention": round(attention, 3),
        "first_impression": fi,
        "image_impressed": bool(ad.visual_quality + taste_match * 0.5 + rng.normal(0, 0.1) > 0.55),
        "caption_read": bool(can_read and attention > 0.3),
        "sentiment": round(sentiment, 3),
        "likely_action": action,
        "comment": comment,
        "comment_topic": topic,
        "purchase_blockers": blockers,
        "reason": "; ".join(reason_bits)[:240],
    }


def priors_from_reactions(reactions: list[dict[str, Any] | None], k: int) -> ReactionPriors:
    """Build arrays from a list (index = archetype idx) of reaction dicts. Missing entries get neutral priors."""
    attention = np.full(k, 0.3, dtype=np.float32)
    sentiment = np.zeros(k, dtype=np.float32)
    action = np.zeros((k, len(ACTIONS)), dtype=np.float32)
    blockers = np.zeros((k, len(BLOCKERS)), dtype=np.float32)
    caption_read = np.full(k, 0.5, dtype=np.float32)
    image_impressed = np.full(k, 0.5, dtype=np.float32)
    topics: list[str | None] = [None] * k
    comments: list[str | None] = [None] * k
    reasons: list[str] = [""] * k
    firsts: list[str] = [""] * k
    raw: list[dict[str, Any]] = [{} for _ in range(k)]
    for i in range(k):
        r = reactions[i] if i < len(reactions) else None
        if not r:
            continue
        raw[i] = r
        attention[i] = float(np.clip(r.get("attention", 0.3), 0.0, 1.0))
        sentiment[i] = float(np.clip(r.get("sentiment", 0.0), -1.0, 1.0))
        a = str(r.get("likely_action", "skip"))
        if a in ACTIONS:
            action[i, ACTIONS.index(a)] = 1.0
        else:
            action[i, 0] = 1.0
        for b in r.get("purchase_blockers") or []:
            if b in BLOCKERS:
                blockers[i, BLOCKERS.index(b)] = 1.0
        caption_read[i] = 1.0 if r.get("caption_read") else 0.0
        image_impressed[i] = 1.0 if r.get("image_impressed") else 0.0
        t = r.get("comment_topic")
        topics[i] = t if t in COMMENT_TOPICS else None
        c = r.get("comment")
        comments[i] = str(c) if c else None
        reasons[i] = str(r.get("reason", ""))
        firsts[i] = str(r.get("first_impression", ""))
    return ReactionPriors(
        attention=attention,
        sentiment=sentiment,
        action=action,
        blockers=blockers,
        caption_read=caption_read,
        image_impressed=image_impressed,
        comment_topic=topics,
        comments=comments,
        reasons=reasons,
        first_impressions=firsts,
        raw=raw,
    )


def positive_share(reactions: list[dict[str, Any] | None]) -> float:
    """Variety guard: share of archetypes with a clearly positive reaction."""
    vals = [r for r in reactions if r]
    if not vals:
        return 0.0
    pos = sum(
        1
        for r in vals
        if float(r.get("sentiment", 0.0)) > 0.3 and r.get("likely_action") not in ("skip", None)
    )
    return pos / len(vals)