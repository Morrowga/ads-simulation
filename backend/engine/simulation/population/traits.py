"""Profile-driven traits: taste, dietary needs, familiarity, brand relationship, language groups.

Everything here is derived from the category template's `trait_dimensions` and the
test's business-profile snapshot, blended with the country's published defaults.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from engine.simulation.types import BRAND_REL, FAMILIARITY, CategoryConfig, FrozenConfig, LanguageGroup

BRAND_CONSTANTS = {
    "k_month": 40.0,  # people who know the brand per month in business
    "reviews_factor": 8.0,
    "aware_min": 0.005,
    "aware_max": 0.60,
    "tried_base": 0.15,
    "tried_per_review": 0.004,
    "tried_min": 0.15,
    "tried_max": 0.70,
    "regular_of_liked": 0.25,
}


def _num(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = d.get(key)
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def brand_awareness_shares(
    profile: dict[str, Any], reach_pool: float, cfg: FrozenConfig | None = None
) -> dict[str, float]:
    """Reputation formula from the Backend document, section 8.2 (constants configurable)."""
    c = dict(BRAND_CONSTANTS)
    if cfg is not None:
        c.update({k: float(v) for k, v in (cfg.settings.get("brand_constants") or {}).items()})
    followers = _num(profile, "followers", 0.0)
    reviews = _num(profile, "review_count", 0.0)
    rating = profile.get("rating")
    months = _num(profile, "months_in_business", 0.0)
    known = followers + c["reviews_factor"] * reviews + months * c["k_month"]
    reach_pool = max(float(reach_pool), 1.0)
    aware_share = float(np.clip(known / reach_pool, c["aware_min"], c["aware_max"]))
    tried_share = float(
        np.clip(c["tried_base"] + c["tried_per_review"] * reviews, c["tried_min"], c["tried_max"])
    )
    try:
        rating_f = float(rating) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating_f = None
    liked_share = float(np.clip((rating_f - 1.0) / 4.0, 0.2, 0.95)) if rating_f else 0.7
    regular_share = c["regular_of_liked"] * liked_share
    # absolute shares over the population
    aware = aware_share
    tried = aware * tried_share
    liked = tried * liked_share
    regular = tried * regular_share
    tried_liked = max(liked - regular, 0.0)
    tried_disliked = max(tried - liked, 0.0)
    aware_not_tried = max(aware - tried, 0.0)
    unaware = max(1.0 - aware, 0.0)
    shares = {
        "unaware": unaware,
        "aware_not_tried": aware_not_tried,
        "tried_liked": tried_liked,
        "tried_disliked": tried_disliked,
        "regular": regular,
    }
    total = sum(shares.values()) or 1.0
    return {k: v / total for k, v in shares.items()}


def sample_brand_relationship(
    rng: np.random.Generator, n: int, shares: dict[str, float], audience_kind: str, post_type: str
) -> np.ndarray:
    """Audience mix by post type (8.9): paid = targeted pool mostly unaware, boosted = followers + pool,
    organic = followers and people who know the brand."""
    p = np.array([shares.get(k, 0.0) for k in BRAND_REL], dtype=np.float64)
    if audience_kind == "followers" or post_type == "organic":
        # everyone in an organic/follower audience knows the brand
        p[0] = p[0] * 0.15
    elif post_type == "boosted":
        p[0] = p[0] * 0.6
    p = p / p.sum()
    return rng.choice(len(BRAND_REL), size=n, p=p).astype(np.int8)


def familiarity_shares(category: CategoryConfig, profile: dict[str, Any]) -> dict[str, float]:
    mixes = category.default_mixes or {}
    raw = profile.get("customer_mix")

    # customer_mix is a multiselect (list of keys), but older data / other categories may hold a
    # single string or an inline dict of shares. Normalise all three shapes.
    mix_list: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        mix_list = [raw]
    else:
        if isinstance(raw, str):
            keys = [raw]
        elif isinstance(raw, (list, tuple, set)):
            keys = [k for k in raw if isinstance(k, str)]
        else:
            keys = []
        mix_list = [mixes[k] for k in keys if k in mixes]

    if not mix_list and mixes:
        mix_list = [mixes.get("default") or next(iter(mixes.values()))]

    out = {k: 0.0 for k in FAMILIARITY}
    if not mix_list:
        out.update(
            {"grew_up_with_it": 0.6, "tried_elsewhere": 0.25, "foreigner_likes_it": 0.05, "never_tried": 0.10}
        )
    else:
        # Equal-weight average of the selected customer groups.
        for mix in mix_list:
            for k in FAMILIARITY:
                out[k] += float(mix.get(k, 0.0)) / len(mix_list)
    total = sum(out.values()) or 1.0
    return {k: v / total for k, v in out.items()}


def taste_dimension(category: CategoryConfig) -> dict[str, Any] | None:
    for dim in category.trait_dimensions:
        if dim.get("kind") == "vector":
            return dim
    return None


def dietary_dimension(category: CategoryConfig) -> dict[str, Any] | None:
    for dim in category.trait_dimensions:
        if dim.get("kind") == "categorical" and dim.get("key") in ("dietary", "dietary_needs"):
            return dim
    return None


def sample_taste(
    rng: np.random.Generator,
    n: int,
    category: CategoryConfig,
    familiarity: np.ndarray,
    profile: dict[str, Any],
) -> tuple[np.ndarray, list[str]]:
    dim = taste_dimension(category)
    if dim is None:
        return np.zeros((n, 0), dtype=np.float32), []
    names = [str(v) for v in dim.get("values", [])]
    dist = dim.get("default_distribution") or {}
    shifts = dim.get("familiarity_shift") or {
        "grew_up_with_it": 0.10,
        "tried_elsewhere": 0.0,
        "foreigner_likes_it": -0.05,
        "never_tried": -0.15,
    }
    out = np.zeros((n, len(names)), dtype=np.float32)
    for j, name in enumerate(names):
        d = dist.get(name, {}) if isinstance(dist, dict) else {}
        mean = float(d.get("mean", 0.5))
        sd = float(d.get("sd", 0.2))
        col = rng.normal(mean, sd, size=n)
        for fi, fname in enumerate(FAMILIARITY):
            col[familiarity == fi] += float(shifts.get(fname, 0.0))
        out[:, j] = np.clip(col, 0.0, 1.0)
    return out, names


def sample_dietary(
    rng: np.random.Generator, n: int, category: CategoryConfig
) -> tuple[np.ndarray, list[str]]:
    dim = dietary_dimension(category)
    if dim is None:
        return np.zeros(n, dtype=np.int8), ["none"]
    names = [str(v) for v in dim.get("values", ["none"])]
    dist = dim.get("default_distribution") or {}
    p = np.array([float(dist.get(nm, 0.0)) for nm in names], dtype=np.float64)
    if p.sum() <= 0:
        p = np.ones(len(names))
    p = p / p.sum()
    return rng.choice(len(names), size=n, p=p).astype(np.int8), names


def blended_language_groups(
    groups: list[LanguageGroup], profile: dict[str, Any], audience: dict[str, Any]
) -> list[LanguageGroup]:
    """Country language shares blended with the profile's customer languages and audience targeting languages."""
    langs = [str(x) for x in (profile.get("customer_languages") or [])]
    target_langs = [str(x) for x in ((audience.get("targeting") or {}).get("languages") or [])]
    if not langs and not target_langs:
        return groups
    boost = set(langs) | set(target_langs)
    out = []
    for g in groups:
        share = g.share
        if g.code in boost or any(lang in boost for lang in g.reading_languages[:1]):
            share = share * 1.0 + 0.15
        else:
            share = share * 0.7
        out.append(LanguageGroup(g.code, g.name, share, list(g.reading_languages)))
    total = sum(g.share for g in out) or 1.0
    for g in out:
        g.share /= total
    return out


def profile_summary(profile: dict[str, Any], category: CategoryConfig) -> str:
    """Short English description of the business used in prompts and reports."""
    name = profile.get("business_name") or profile.get("name") or "the business"
    parts = [f"{name} ({category.name})"]
    for key in ("cuisine", "what_you_sell", "price_level", "location_type", "style", "product_type"):
        v = profile.get(key)
        if v:
            parts.append(f"{key.replace('_', ' ')}: {v}")
    followers = profile.get("followers")
    if followers not in (None, ""):
        parts.append(f"followers: {int(_num(profile, 'followers'))}")
    rating = profile.get("rating")
    if rating not in (None, ""):
        parts.append(f"rating: {rating} from {int(_num(profile, 'review_count'))} reviews")
    months = profile.get("months_in_business")
    if months not in (None, ""):
        parts.append(f"{int(_num(profile, 'months_in_business'))} months in business")
    return "; ".join(parts)
