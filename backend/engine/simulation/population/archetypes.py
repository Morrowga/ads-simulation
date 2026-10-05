"""Group agents into ~200 archetypes with seeded k-means and describe each one for the LLM."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import KMeans

from engine.simulation.types import (
    BRAND_REL,
    FAMILIARITY,
    GENDERS,
    INCOME_BANDS,
    TRAIT_NAMES,
    ArchetypeTable,
    Population,
    age_band_label,
)


def feature_matrix(pop: Population) -> np.ndarray:
    cols = [
        pop.traits,
        (pop.age.astype(np.float32) / 70.0)[:, None],
        (pop.income_band.astype(np.float32) / 3.0)[:, None],
        (pop.brand_rel.astype(np.float32) / 4.0)[:, None] * 1.5,
        (pop.familiarity.astype(np.float32) / 3.0)[:, None],
        pop.is_follower.astype(np.float32)[:, None],
        (pop.language_group.astype(np.float32) / max(1, len(pop.language_group_codes) - 1))[:, None] * 1.2,
        pop.sessions_per_day[:, None] / 20.0,
    ]
    if pop.taste.shape[1]:
        cols.append(pop.taste)
    if pop.interests.shape[1]:
        cols.append(pop.interests[:, : min(6, pop.interests.shape[1])] * 0.5)
    x = np.concatenate(cols, axis=1).astype(np.float32)
    mean = x.mean(axis=0)
    sd = x.std(axis=0) + 1e-6
    return (x - mean) / sd


def build_archetypes(pop: Population, k: int, seed: int) -> ArchetypeTable:
    k = int(max(2, min(k, pop.n // 5 if pop.n >= 10 else 2)))
    x = feature_matrix(pop)
    km = KMeans(n_clusters=k, random_state=int(seed) % (2**32 - 1), n_init=1, max_iter=60, algorithm="lloyd")
    labels = km.fit_predict(x).astype(np.int16)
    sizes = np.bincount(labels, minlength=k).astype(np.int32)
    pop.archetype = labels
    profiles = [describe_archetype(pop, labels, i) for i in range(k)]
    return ArchetypeTable(
        k=k, labels=labels, sizes=sizes, profiles=profiles, features=km.cluster_centers_.astype(np.float32)
    )


def _mode(values: np.ndarray) -> int:
    if values.shape[0] == 0:
        return 0
    return int(np.bincount(values.astype(np.int64)).argmax())


def _level(v: float) -> str:
    if v < 0.33:
        return "low"
    if v < 0.66:
        return "medium"
    return "high"


def describe_archetype(pop: Population, labels: np.ndarray, i: int) -> dict[str, Any]:
    mask = labels == i
    n = int(mask.sum())
    if n == 0:
        return {"idx": i, "size": 0, "label": f"Empty archetype {i}"}
    traits = pop.traits[mask].mean(axis=0)
    trait_map = {name: round(float(traits[j]), 2) for j, name in enumerate(TRAIT_NAMES)}
    age_mean = float(pop.age[mask].mean())
    band = age_band_label(_mode(np.array([b for b in _age_bands(pop.age[mask])])))
    gender = GENDERS[_mode(pop.gender[mask])]
    income = INCOME_BANDS[_mode(pop.income_band[mask])]
    brand = BRAND_REL[_mode(pop.brand_rel[mask])]
    fam = FAMILIARITY[_mode(pop.familiarity[mask])]
    lang_idx = _mode(pop.language_group[mask])
    lang = pop.language_group_codes[lang_idx]
    lang_name = str(pop.extra.get("language_group_names", np.array(pop.language_group_codes))[lang_idx])
    reads = [pop.language_codes[j] for j in np.where(pop.reading_langs[mask].mean(axis=0) > 0.5)[0]]
    taste = {
        nm: round(float(v), 2) for nm, v in zip(pop.taste_names, pop.taste[mask].mean(axis=0), strict=False)
    }
    dietary = pop.dietary_names[_mode(pop.dietary[mask])] if pop.dietary_names else "none"
    top_interests = np.argsort(-pop.interests[mask].mean(axis=0))[:3]
    interests = [pop.interest_names[j] for j in top_interests]
    follower_share = float(pop.is_follower[mask].mean())
    descriptors = []
    if trait_map["impulsiveness"] > 0.6:
        descriptors.append("impulsive")
    if trait_map["patience"] < 0.35:
        descriptors.append("impatient")
    if trait_map["skepticism"] > 0.6:
        descriptors.append("skeptical")
    if trait_map["price_sensitivity"] > 0.62:
        descriptors.append("price-sensitive")
    if trait_map["social"] > 0.62:
        descriptors.append("social")
    if trait_map["brand_loyalty"] > 0.62:
        descriptors.append("loyal")
    if not descriptors:
        descriptors.append("balanced")
    label = (
        f"{gender.upper()} {band} · {', '.join(descriptors[:2])} · {brand.replace('_', ' ')} · {lang_name}"
    )
    return {
        "idx": i,
        "size": n,
        "label": label,
        "age_band": band,
        "age_mean": round(age_mean, 1),
        "gender": gender,
        "income_band": income,
        "traits": trait_map,
        "descriptors": descriptors,
        "brand_relationship": brand,
        "familiarity": fam,
        "language_group": lang,
        "language_group_name": lang_name,
        "reads": reads,
        "taste": taste,
        "dietary": dietary,
        "interests": interests,
        "follower_share": round(follower_share, 2),
        "share_of_population": round(n / pop.n, 4),
    }


def _age_bands(age: np.ndarray) -> np.ndarray:
    from engine.simulation.types import age_band_index

    return age_band_index(age)


def nearest_archetype(table: ArchetypeTable, idx: int, exclude: set[int]) -> int | None:
    """Index of the closest archetype (by centroid distance) not in `exclude`; used for LLM fallbacks."""
    c = table.features[idx]
    d = np.linalg.norm(table.features - c[None, :], axis=1)
    order = np.argsort(d)
    for j in order:
        j = int(j)
        if j != idx and j not in exclude:
            return j
    return None
