"""Population builder: N agents as a structure of arrays from country demographics, targeting,
the business-profile snapshot, the culture layer and per-platform habits."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import sparse

from engine.simulation.config.culture import trait_correlation, trait_means_vector
from engine.simulation.config.platforms import peak_hours, sessions_per_day, user_share_by_age
from engine.simulation.population.traits import (
    blended_language_groups,
    brand_awareness_shares,
    familiarity_shares,
    sample_brand_relationship,
    sample_dietary,
    sample_taste,
)
from engine.simulation.types import (
    AGE_BANDS,
    FAMILIARITY,
    GENDERS,
    INCOME_BANDS,
    N_TRAITS,
    FrozenConfig,
    Population,
    age_band_index,
    age_band_label,
)

GENERIC_INTERESTS = [
    "food",
    "fashion",
    "beauty",
    "shopping",
    "travel",
    "gaming",
    "sports",
    "music",
    "family",
    "tech",
]


def _age_distribution(cfg: FrozenConfig, age_min: int, age_max: int) -> tuple[np.ndarray, np.ndarray]:
    demo = cfg.country.demographics or {}
    raw = demo.get("age_bands") or {}
    p = np.zeros(len(AGE_BANDS), dtype=np.float64)
    for i, (lo, hi) in enumerate(AGE_BANDS):
        share = raw.get(age_band_label(i))
        if share is None:
            share = [0.06, 0.16, 0.24, 0.22, 0.16, 0.10, 0.06][i]
        overlap = max(0, min(hi, age_max) - max(lo, age_min) + 1) / (hi - lo + 1)
        p[i] = float(share) * overlap
    if p.sum() <= 0:
        p = np.ones(len(AGE_BANDS))
    return p / p.sum(), np.array(AGE_BANDS)


def sample_demographics(
    cfg: FrozenConfig, targeting: dict[str, Any], rng: np.random.Generator, n: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    age_min = int(targeting.get("age_min", 18))
    age_max = int(targeting.get("age_max", 55))
    p, bands = _age_distribution(cfg, age_min, age_max)
    band = rng.choice(len(bands), size=n, p=p)
    lo = np.maximum(bands[band, 0], age_min)
    hi = np.minimum(bands[band, 1], age_max)
    hi = np.maximum(hi, lo)
    age = (lo + np.floor(rng.random(n) * (hi - lo + 1))).astype(np.int16)

    demo = cfg.country.demographics or {}
    g_raw = demo.get("gender") or {"f": 0.51, "m": 0.47, "other": 0.02}
    allowed = [g for g in (targeting.get("genders") or list(GENDERS)) if g in GENDERS] or list(GENDERS)
    gp = np.array([float(g_raw.get(g, 0.0)) if g in allowed else 0.0 for g in GENDERS], dtype=np.float64)
    if gp.sum() <= 0:
        gp = np.array([1.0 if g in allowed else 0.0 for g in GENDERS])
    gender = rng.choice(len(GENDERS), size=n, p=gp / gp.sum()).astype(np.int8)

    inc_raw = demo.get("income_bands") or {"low": 0.3, "lower_mid": 0.35, "upper_mid": 0.25, "high": 0.1}
    ip = np.array([float(inc_raw.get(b, 0.0)) for b in INCOME_BANDS], dtype=np.float64)
    if ip.sum() <= 0:
        ip = np.ones(len(INCOME_BANDS))
    income = rng.choice(len(INCOME_BANDS), size=n, p=ip / ip.sum()).astype(np.int8)
    return age, gender, income


def sample_traits(
    cfg: FrozenConfig, rng: np.random.Generator, n: int, age: np.ndarray, income: np.ndarray
) -> np.ndarray:
    means = trait_means_vector(cfg.country).astype(np.float64)
    corr = trait_correlation()
    sd = np.full(N_TRAITS, 0.18)
    cov = corr * np.outer(sd, sd)
    traits = rng.multivariate_normal(means, cov, size=n)
    # age effects: patience grows with age, impulsiveness falls; never from gender
    age_f = (age.astype(np.float64) - 35.0) / 40.0
    traits[:, 0] += 0.12 * age_f
    traits[:, 1] -= 0.12 * age_f
    # income effect on price sensitivity
    traits[:, 5] -= 0.08 * (income.astype(np.float64) - 1.5)
    return np.clip(traits, 0.0, 1.0).astype(np.float32)


def sample_interests(
    cfg: FrozenConfig, rng: np.random.Generator, n: int, targeting: dict[str, Any]
) -> tuple[np.ndarray, list[str]]:
    names = list(dict.fromkeys(GENERIC_INTERESTS + [t for t in cfg.category.tags if t]))
    k = len(names)
    w = rng.dirichlet(np.ones(k) * 0.6, size=n).astype(np.float32)
    # targeting interests: people in the pool care more about them
    for t in targeting.get("interests") or []:
        if t in names:
            j = names.index(t)
            w[:, j] += rng.random(n).astype(np.float32) * 0.5
    # category tags get a moderate bump (the targeted pool is at least somewhat related)
    for t in cfg.category.tags:
        if t in names:
            j = names.index(t)
            w[:, j] += 0.15
    w = w / np.maximum(w.sum(axis=1, keepdims=True), 1e-6)
    return w, names


def build_friend_graph(
    rng: np.random.Generator, n: int, k: int = 8, rewire_p: float = 0.1
) -> sparse.csr_matrix:
    """Watts–Strogatz style small-world graph as a CSR matrix (row i = friends of i)."""
    if n < 4:
        return sparse.csr_matrix((n, n), dtype=np.float32)
    k = max(2, min(k, n - 1))
    half = k // 2
    rows = np.repeat(np.arange(n), half)
    offsets = np.tile(np.arange(1, half + 1), n)
    cols = (rows + offsets) % n
    rewire = rng.random(rows.shape[0]) < rewire_p
    cols[rewire] = rng.integers(0, n, size=int(rewire.sum()))
    keep = cols != rows
    rows, cols = rows[keep], cols[keep]
    data = np.ones(rows.shape[0], dtype=np.float32)
    m = sparse.coo_matrix((data, (rows, cols)), shape=(n, n))
    m = (m + m.T).tocsr()
    m.data[:] = 1.0
    return m


def build_population(
    cfg: FrozenConfig,
    platform_code: str,
    audience: dict[str, Any],
    n: int,
    seed: int,
) -> Population:
    rng = np.random.default_rng(seed)
    platform = cfg.platforms[platform_code]
    targeting = dict(audience.get("targeting") or {})
    audience_kind = str(audience.get("kind", "targeted"))
    profile = cfg.profile

    age, gender, income = sample_demographics(cfg, targeting, rng, n)
    traits = sample_traits(cfg, rng, n, age, income)
    interests, interest_names = sample_interests(cfg, rng, n, targeting)

    # platform habits
    share_by_age = user_share_by_age(platform)
    band = age_band_index(age)
    uses_platform = rng.random(n) < share_by_age[band]
    base_hours = peak_hours(platform)
    noise = rng.normal(1.0, 0.25, size=(n, 24)).astype(np.float32)
    active = np.clip(base_hours[None, :] * noise, 0.0, 1.0)
    # personal daily activity level: sessions/day scales the whole curve
    spd = sessions_per_day(platform, rng, n)
    level = np.clip(spd / 6.0, 0.3, 2.0)[:, None].astype(np.float32)
    active = np.clip(active * level * 0.35, 0.0, 0.95).astype(np.float32)
    scroll_speed = np.clip(rng.normal(1.0, 0.2, size=n), 0.5, 1.6).astype(np.float32)

    # languages
    groups = blended_language_groups(cfg.country.language_groups, profile, audience)
    gp = np.array([g.share for g in groups], dtype=np.float64)
    gp = gp / gp.sum()
    language_group = rng.choice(len(groups), size=n, p=gp).astype(np.int8)
    lang_codes = list(cfg.country.languages)
    for g in groups:
        for lang in g.reading_languages:
            if lang not in lang_codes:
                lang_codes.append(lang)
    reading = np.zeros((n, len(lang_codes)), dtype=bool)
    for gi, g in enumerate(groups):
        mask = language_group == gi
        for lang in g.reading_languages:
            reading[mask, lang_codes.index(lang)] = True
    # a share of every group also reads English (education / expats), country-configurable
    en_extra = float((cfg.country.culture or {}).get("english_reading_share", 0.3))
    if "en" in lang_codes:
        reading[:, lang_codes.index("en")] |= rng.random(n) < en_extra

    # category-specific traits
    fam_shares = familiarity_shares(cfg.category, profile)
    fp = np.array([fam_shares[k] for k in FAMILIARITY], dtype=np.float64)
    familiarity = rng.choice(len(FAMILIARITY), size=n, p=fp / fp.sum()).astype(np.int8)
    taste, taste_names = sample_taste(rng, n, cfg.category, familiarity, profile)
    dietary, dietary_names = sample_dietary(rng, n, cfg.category)

    # brand relationship from the reputation formula
    audience_size = float(targeting.get("audience_size") or _default_audience_size(cfg))
    shares = brand_awareness_shares(profile, audience_size, cfg)
    brand_rel = sample_brand_relationship(rng, n, shares, audience_kind, cfg.test.post_type)
    scale = max(audience_size / n, 1.0)
    followers_real = float(profile.get("followers") or 0)
    follower_agents = int(min(n, round(followers_real / scale)))
    is_follower = np.zeros(n, dtype=bool)
    if follower_agents > 0:
        # followers are drawn first from people who know the brand
        known = np.where(brand_rel > 0)[0]
        pick = rng.permutation(known)[:follower_agents]
        is_follower[pick] = True
        remaining = follower_agents - pick.shape[0]
        if remaining > 0:
            others = np.where(~is_follower)[0]
            is_follower[rng.permutation(others)[:remaining]] = True
        brand_rel[is_follower & (brand_rel == 0)] = 1

    friends = build_friend_graph(rng, n, k=int(cfg.settings.get("friend_graph_k", 8)), rewire_p=0.1)

    return Population(
        n=n,
        age=age,
        gender=gender,
        income_band=income,
        traits=traits,
        interests=interests,
        interest_names=interest_names,
        active_hours=active,
        sessions_per_day=spd,
        scroll_speed=scroll_speed,
        uses_platform=uses_platform,
        language_group=language_group,
        language_group_codes=[g.code for g in groups],
        reading_langs=reading,
        language_codes=lang_codes,
        taste=taste,
        taste_names=taste_names,
        dietary=dietary,
        dietary_names=dietary_names,
        familiarity=familiarity,
        brand_rel=brand_rel,
        is_follower=is_follower,
        archetype=np.zeros(n, dtype=np.int16),
        friends=friends,
        scale=scale,
        extra={"language_group_names": np.array([g.name for g in groups])},
    )


def _default_audience_size(cfg: FrozenConfig) -> float:
    demo = cfg.country.demographics or {}
    online = float(demo.get("online_population", 5_000_000))
    # a local business reaches a small slice of the online population
    return max(20_000.0, online * 0.004)
