"""Engine data types. Pure Python + NumPy, no web or database imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import sparse

TRAIT_NAMES = (
    "patience",
    "impulsiveness",
    "skepticism",
    "anger",
    "openness",
    "price_sensitivity",
    "social",
    "brand_loyalty",
)
N_TRAITS = len(TRAIT_NAMES)

BRAND_REL = ("unaware", "aware_not_tried", "tried_liked", "tried_disliked", "regular")
FAMILIARITY = ("grew_up_with_it", "tried_elsewhere", "foreigner_likes_it", "never_tried")
GENDERS = ("f", "m", "other")
INCOME_BANDS = ("low", "lower_mid", "upper_mid", "high")
AGE_BANDS = ((13, 17), (18, 24), (25, 34), (35, 44), (45, 54), (55, 64), (65, 99))
ACTIONS = ("skip", "pause", "react", "comment", "click", "message", "buy", "share", "save")
BLOCKERS = ("price", "shipping", "size", "trust", "relevance", "none")
COMMENT_TOPICS = ("price", "product_detail", "service", "positive", "negative", "other")
GOALS = ("sales", "messages", "traffic", "awareness", "engagement")
POST_TYPES = ("paid", "boosted", "organic")

GOAL_METRIC = {
    "sales": "buys",
    "messages": "messages",
    "traffic": "clicks",
    "awareness": "noticed",
    "engagement": "engagements",
}
GOAL_RATE = {
    "sales": "buy_rate",
    "messages": "message_rate",
    "traffic": "ctr",
    "awareness": "stop_rate",
    "engagement": "engagement_rate",
}


def age_band_index(age: np.ndarray) -> np.ndarray:
    idx = np.zeros(age.shape, dtype=np.int8)
    for i, (lo, hi) in enumerate(AGE_BANDS):
        idx[(age >= lo) & (age <= hi)] = i
    return idx


def age_band_label(i: int) -> str:
    lo, hi = AGE_BANDS[i]
    return f"{lo}-{hi}" if hi < 99 else f"{lo}+"


@dataclass
class LanguageGroup:
    code: str
    name: str
    share: float
    reading_languages: list[str]


@dataclass
class ScenarioSpec:
    code: str
    name: str
    mood: float = 0.0
    competition: float = 1.0
    activity: float = 1.0
    buy_boost: float = 0.0
    discount_norm: float = 1.0
    weight: float = 1.0
    description: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScenarioSpec:
        m = d.get("modifiers", d)
        return cls(
            code=d.get("code", "normal"),
            name=d.get("name", d.get("code", "normal")),
            mood=float(m.get("mood", 0.0)),
            competition=float(m.get("competition", 1.0)),
            activity=float(m.get("activity", 1.0)),
            buy_boost=float(m.get("buy_boost", 0.0)),
            discount_norm=float(m.get("discount_norm", 1.0)),
            weight=float(d.get("weight", 1.0)),
            description=str(d.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "modifiers": {
                "mood": self.mood,
                "competition": self.competition,
                "activity": self.activity,
                "buy_boost": self.buy_boost,
                "discount_norm": self.discount_norm,
            },
            "weight": self.weight,
        }


@dataclass
class PlatformConfig:
    code: str
    name: str
    status: str
    placements: dict[str, dict[str, Any]]
    behavior: dict[str, Any]
    organic: dict[str, Any]
    actions: list[str]
    supported_goals: dict[str, list[str]]
    market: dict[str, Any]
    benchmarks: dict[str, float]
    version: int | None = None

    def placement_spec(self, code: str) -> dict[str, Any] | None:
        return self.placements.get(code)


@dataclass
class CountryConfig:
    code: str
    name: str
    currency: str
    language_groups: list[LanguageGroup]
    languages: list[str]
    culture: dict[str, Any]
    calendar: dict[str, Any]
    demographics: dict[str, Any]
    benchmarks: dict[str, float]
    trait_means: dict[str, float]
    version: int | None = None


@dataclass
class CategoryConfig:
    code: str
    name: str
    trait_dimensions: list[dict[str, Any]]
    activation_rules: list[dict[str, Any]]
    default_mixes: dict[str, Any]
    buying_behavior: dict[str, Any]
    blockers: list[dict[str, Any]]
    trust_signals: list[dict[str, Any]]
    comment_topics: list[str]
    benchmark_adjustments: dict[str, float]
    tags: list[str]
    version: int | None = None


@dataclass
class TierSpec:
    code: str = "standard"
    runs_target: int = 150
    min_runs: int = 60
    scenarios: int = 5
    max_audiences: int = 1
    agents: int = 20000
    archetypes: int = 200


@dataclass
class PlatformSelection:
    code: str
    placements: list[str]
    budget_share: float = 100.0
    settings_version: int | None = None


@dataclass
class TestSpec:
    test_id: str
    post_type: str
    goal: str
    budget_usd: float | None
    schedule: dict[str, Any]
    platforms: list[PlatformSelection]
    audiences: list[dict[str, Any]]
    tier: TierSpec
    ad_copy: dict[str, Any] = field(default_factory=dict)
    title: str = ""


@dataclass
class AdFeatures:
    hook_strength: float = 0.5
    offer_visible_at_s: float | None = None
    duration_s: float = 3.0
    is_video: bool = False
    key_moments: list[dict[str, Any]] = field(default_factory=list)
    category: str = "other"
    on_screen_text: str = ""
    sound_reliance: float = 0.0
    price_shown: bool = False
    price_level: float = 0.5
    discount_pct: float = 0.0
    trust_signals: list[str] = field(default_factory=list)
    cta: str = "learn_more"
    caption_language: str = "en"
    caption_strength: float = 0.5
    caption_english: str = ""
    taste_profile: dict[str, float] = field(default_factory=dict)
    interest_tags: list[str] = field(default_factory=list)
    description: str = ""
    visual_quality: float = 0.6
    clarity: float = 0.6
    novelty: float = 0.5  # 0 = seen it a hundred times, 1 = genuinely surprising
    genericness: float = 0.5  # 0 = distinctive, 1 = stock / template / could be anyone's ad
    emotional_tone: str = "neutral"

    @property
    def attention_pull(self) -> float:
        """Hook strength adjusted for surprise: a generic, seen-before ad cannot stop people on its hook alone."""
        v = self.hook_strength + 0.25 * (self.novelty - 0.5) - 0.25 * (self.genericness - 0.5)
        return float(min(1.0, max(0.0, v)))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AdFeatures:
        known = {f: d[f] for f in cls.__dataclass_fields__ if f in d}
        obj = cls(**known)
        if obj.offer_visible_at_s is not None:
            obj.offer_visible_at_s = float(obj.offer_visible_at_s)
        obj.duration_s = float(obj.duration_s or 3.0)
        return obj

    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


@dataclass
class Weights:
    behavior: dict[str, float]
    score_by_goal: dict[str, dict[str, float]]
    version: int | None = None

    def b(self, key: str, default: float = 0.0) -> float:
        return float(self.behavior.get(key, default))


@dataclass
class FrozenConfig:
    """Everything the engine needs for one test, resolved from published settings."""

    country: CountryConfig
    category: CategoryConfig
    platforms: dict[str, PlatformConfig]
    scenarios: list[ScenarioSpec]
    weights: Weights
    test: TestSpec
    profile: dict[str, Any]
    versions: dict[str, Any]
    score_benchmarks: dict[str, dict[str, float]] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Population:
    """Structure of arrays for N agents."""

    n: int
    age: np.ndarray  # int16 (N,)
    gender: np.ndarray  # int8 0=f 1=m 2=other
    income_band: np.ndarray  # int8
    traits: np.ndarray  # float32 (N, 8)
    interests: np.ndarray  # float32 (N, K)
    interest_names: list[str]
    active_hours: np.ndarray  # float32 (N, 24)
    sessions_per_day: np.ndarray  # float32 (N,)
    scroll_speed: np.ndarray  # float32 (N,) 0.5-1.5
    uses_platform: np.ndarray  # bool (N,)
    language_group: np.ndarray  # int8 (N,)
    language_group_codes: list[str]
    reading_langs: np.ndarray  # bool (N, L)
    language_codes: list[str]
    taste: np.ndarray  # float32 (N, T)
    taste_names: list[str]
    dietary: np.ndarray  # int8 (N,)
    dietary_names: list[str]
    familiarity: np.ndarray  # int8 (N,) index into FAMILIARITY
    brand_rel: np.ndarray  # int8 (N,) index into BRAND_REL
    is_follower: np.ndarray  # bool (N,)
    archetype: np.ndarray  # int16 (N,)
    friends: sparse.csr_matrix
    scale: float = 1.0  # real people represented by one agent
    extra: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def age_band(self) -> np.ndarray:
        return age_band_index(self.age)


@dataclass
class ArchetypeTable:
    k: int
    labels: np.ndarray  # int16 (N,)
    sizes: np.ndarray  # int32 (K,)
    profiles: list[dict[str, Any]]  # human/LLM readable summary per archetype
    features: np.ndarray  # float32 (K, F) centroids


@dataclass
class ReactionPriors:
    """Per-archetype priors derived from LLM reactions (K archetypes)."""

    attention: np.ndarray  # (K,) 0-1
    sentiment: np.ndarray  # (K,) -1..1
    action: np.ndarray  # (K, len(ACTIONS)) one-hot-ish likelihoods
    blockers: np.ndarray  # (K, len(BLOCKERS))
    caption_read: np.ndarray  # (K,) 0/1
    image_impressed: np.ndarray  # (K,) 0/1
    comment_topic: list[str | None]
    comments: list[str | None]
    reasons: list[str]
    first_impressions: list[str]
    raw: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExposureResult:
    idx: np.ndarray
    stop: np.ndarray
    watch_s: np.ndarray
    saw_offer: np.ndarray
    react: np.ndarray
    comment: np.ndarray
    share: np.ndarray
    save: np.ndarray
    click: np.ndarray
    message: np.ndarray
    buy: np.ndarray
    blocker: np.ndarray  # int8 index into BLOCKERS or -1
