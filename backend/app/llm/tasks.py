"""LLM tasks used by the worker and admin services: ad analysis, archetype reactions,
comment classification, reason writing, category drafting."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

from app.llm import prompts
from app.llm.client import InvalidJSONError, LLMClient
from app.llm.schemas import SCHEMAS
from engine.simulation.results.evidence import validate_reasons
from engine.simulation.reaction.priors import heuristic_reaction, positive_share
from engine.simulation.population.traits import profile_summary
from engine.simulation.types import AdFeatures, ArchetypeTable, FrozenConfig, ScenarioSpec

POST_LABEL = {
    "paid": "a sponsored ad",
    "boosted": "a boosted (sponsored) post",
    "organic": "a regular post from a page you follow or a friend shared",
}


def _culture_notes(cfg: FrozenConfig) -> str:
    c = cfg.country.culture or {}
    parts = []
    sense = c.get("ad_sense") or {}
    if sense.get("likes"):
        parts.append("People respond to: " + ", ".join(str(x) for x in sense["likes"]))
    if sense.get("dislikes"):
        parts.append("People dislike: " + ", ".join(str(x) for x in sense["dislikes"]))
    if c.get("price_sensitivity") is not None:
        parts.append(
            f"Price sensitivity {c.get('price_sensitivity')}/1; skepticism towards sponsored posts {c.get('sponsored_skepticism', 0.5)}/1"
        )
    tone = c.get("tone") or {}
    if tone:
        parts.append("Tone preferences: " + ", ".join(f"{k} {v}" for k, v in tone.items()))
    cm = c.get("colour_meanings") or {}
    if cm:
        parts.append("Colour meanings: " + "; ".join(f"{k}: {v}" for k, v in list(cm.items())[:5]))
    return "\n".join(parts) or "No special notes."


# --------------------------------------------------------------------------- ad analysis

ANALYZE_SAMPLES = max(1, int(os.environ.get("ANALYZE_SAMPLES", "3")))

def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def merge_feature_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Several analyses of the same ad -> one. Every numeric feature takes its median across the samples
    (with an odd count the median is one of the values the model actually returned, so it stays on the same
    0.05 grid). Text and list fields come from the sample closest to the medians."""
    if len(samples) == 1:
        return samples[0]
    keys = [k for k in samples[0] if all(_is_num(s.get(k)) for s in samples)]
    med = {k: sorted(s[k] for s in samples)[len(samples) // 2] for k in keys}
    base = min(samples, key=lambda s: sum(abs(s[k] - med[k]) for k in keys))
    out = dict(base)
    out.update(med)
    return out

async def analyze_ad(
    client: LLMClient,
    cfg: FrozenConfig,
    *,
    caption: str,
    headline: str,
    cta: str,
    assets: list[dict[str, Any]],
    images: list[bytes],
    transcript: str,
) -> tuple[dict[str, Any], str]:
    hints = {}
    for dim in cfg.category.trait_dimensions:
        if dim.get("kind") == "vector":
            hints["taste_dimensions"] = dim.get("values", [])
    look_for = ", ".join(str(x) for x in (cfg.settings.get("analyzer_look_for") or []))
    text, version = prompts.render(
        "ad_analysis",
        category_name=cfg.category.name,
        country_name=cfg.country.name,
        taste_dimensions=hints.get("taste_dimensions") or ["practical", "emotional", "status", "fun"],
        look_for=look_for or "the main product, price, offer, contact, location",
        caption=caption,
        headline=headline,
        cta=cta,
        media_summary=[
            f"{a.get('kind')} {a.get('width')}x{a.get('height')}"
            + (f" {a.get('duration_s')}s" if a.get("duration_s") else "")
            for a in assets
        ],
        transcript=transcript,
    )
    profile_taste = (
        cfg.profile.get("taste_profile") if isinstance(cfg.profile.get("taste_profile"), dict) else {}
    )
    context = {
        "caption": caption,
        "headline": headline,
        "cta": cta,
        "assets": assets,
        "transcript": transcript,
        "profile_taste": profile_taste,
        "category": {
            "code": cfg.category.code,
            "name": cfg.category.name,
            "tags": cfg.category.tags,
            "analyzer_hints": {"taste_dimensions": hints.get("taste_dimensions", [])},
        },
    }
    calls = [
        client.complete_json(
            stage="analyze_ad",
            kind="smart",
            system="You analyze social media ads and return strict JSON.",
            user=text,
            schema_name="ad_analysis",
            schema=SCHEMAS["ad_analysis"],
            temperature=0.1,
            images=images,
            context=context,
            prompt_version=version,
        )
        for _ in range(ANALYZE_SAMPLES)
    ]
    raw = await asyncio.gather(*calls, return_exceptions=True)
    ok = [r for r in raw if not isinstance(r, BaseException)]
    if not ok:
        raise next(r for r in raw if isinstance(r, BaseException))
    features = merge_feature_samples([features_from_analysis(d, assets, cta) for d in ok])
    return features, version


def _unit(value: Any, default: float) -> float:
    try:
        return float(min(1.0, max(0.0, float(value))))
    except (TypeError, ValueError):
        return default


def features_from_analysis(
    data: dict[str, Any], assets: list[dict[str, Any]], declared_cta: str
) -> dict[str, Any]:
    video = next((a for a in assets if a.get("kind") == "video"), None)
    taste = {}
    for d in (data.get("taste_profile") or {}).get("dims") or []:
        try:
            taste[str(d["name"])] = float(min(1.0, max(0.0, float(d["value"]))))
        except (KeyError, TypeError, ValueError):
            continue
    hook = _unit(data.get("hook_strength"), 0.5)
    novelty = _unit(data.get("novelty"), 0.5)
    genericness = _unit(data.get("genericness"), 0.5)
    caption_strength = _unit(data.get("caption_strength"), 0.5)
    signals = [str(s) for s in (data.get("generic_signals") or []) if s and s != "none"]
    # guards: a generic-looking ad cannot hold a high hook, and a one-word caption adds almost nothing
    if len(signals) >= 2 or genericness >= 0.75:
        hook = min(hook, 0.5)
    if len(str(data.get("caption_english") or "").split()) <= 2:
        caption_strength = min(caption_strength, 0.15)
    features = {
        "hook_strength": hook,
        "novelty": novelty,
        "genericness": genericness,
        "offer_visible_at_s": data.get("offer_visible_at_s"),
        "duration_s": float(video.get("duration_s") or 8.0) if video else 3.0,
        "is_video": video is not None,
        "key_moments": data.get("key_moments") or [],
        "category": str(data.get("category") or "other"),
        "on_screen_text": str(data.get("on_screen_text") or ""),
        "sound_reliance": _unit(data.get("sound_reliance"), 0.0),
        "price_shown": bool(data.get("price_shown")),
        "price_level": _unit(data.get("price_level"), 0.5),
        "discount_pct": float(max(0.0, data.get("discount_pct", 0.0))),
        "trust_signals": [str(x) for x in (data.get("trust_signals") or [])],
        "cta": str(data.get("cta") or declared_cta or "learn_more"),
        "caption_language": str(data.get("caption_language") or "en")[:8].lower(),
        "caption_strength": caption_strength,
        "caption_english": str(data.get("caption_english") or ""),
        "taste_profile": taste,
        "interest_tags": [str(x) for x in (data.get("interest_tags") or [])],
        "description": str(data.get("description") or ""),
        "visual_quality": _unit(data.get("visual_quality"), 0.6),
        "clarity": _unit(data.get("clarity"), 0.6),
        "emotional_tone": str(data.get("emotional_tone") or "neutral"),
        "generic_signals": signals,
        "first_glance": str(data.get("first_glance") or ""),
    }
    if declared_cta and declared_cta != "none":
        features["cta"] = declared_cta
    return features


# --------------------------------------------------------------------------- reactions


def reaction_system_prompt(
    cfg: FrozenConfig,
    ad: AdFeatures,
    platform_code: str,
    placement: str,
    scenario: ScenarioSpec,
    caption_original: str,
) -> tuple[str, str]:
    platform = cfg.platforms[platform_code]
    return prompts.render(
        "reaction_system",
        platform_name=platform.name,
        country_name=cfg.country.name,
        placement=placement,
        sound_default=platform.behavior.get("sound_default", "off"),
        avg_seconds_per_post=platform.behavior.get("avg_seconds_per_post", 1.7),
        post_label=POST_LABEL.get(cfg.test.post_type, "a post"),
        culture_notes=_culture_notes(cfg),
        ad_description=ad.description,
        key_moments=[f"{m.get('t')}s: {m.get('label')}" for m in ad.key_moments],
        on_screen_text=ad.on_screen_text,
        caption_language=ad.caption_language,
        caption_english=ad.caption_english,
        caption_original=caption_original,
        cta=ad.cta,
        price_shown=ad.price_shown,
        discount_pct=ad.discount_pct,
        trust_signals=ad.trust_signals,
        scenario_name=scenario.name,
        scenario_description=scenario.description or "",
        mood=scenario.mood,
        competition=scenario.competition,
    )


def reaction_user_prompt(
    cfg: FrozenConfig, profile: dict[str, Any], scenario: ScenarioSpec, times_seen: int = 0
) -> str:
    traits = profile.get("traits", {})
    mood_word = "good" if scenario.mood > 0.1 else ("low" if scenario.mood < -0.1 else "normal")
    text, _ = prompts.render(
        "reaction_user",
        profile_summary=profile_summary(cfg.profile, cfg.category),
        brand_relationship=str(profile.get("brand_relationship", "unaware")).replace("_", " "),
        taste=profile.get("taste") or {},
        familiarity=str(profile.get("familiarity", "never_tried")).replace("_", " "),
        reads=profile.get("reads") or ["en"],
        gender={"f": "woman", "m": "man", "other": "person"}.get(str(profile.get("gender")), "person"),
        age_band=profile.get("age_band", "25-34"),
        income_band=str(profile.get("income_band", "lower_mid")).replace("_", " "),
        patience=traits.get("patience", 0.5),
        impulsiveness=traits.get("impulsiveness", 0.5),
        skepticism=traits.get("skepticism", 0.5),
        anger=traits.get("anger", 0.3),
        price_sensitivity=traits.get("price_sensitivity", 0.5),
        social=traits.get("social", 0.5),
        openness=traits.get("openness", 0.5),
        interests=profile.get("interests") or [],
        dietary=profile.get("dietary", "none"),
        is_follower=float(profile.get("follower_share", 0)) > 0.5,
        day="Saturday" if scenario.code in ("payday", "sale_season") else "Wednesday",
        hour=19,
        mood_word=mood_word,
        situation=scenario.description or "scrolling on the phone after work",
        times_seen=times_seen,
    )
    return text


async def react_archetypes(
    client: LLMClient,
    cfg: FrozenConfig,
    ad: AdFeatures,
    table: ArchetypeTable,
    platform_code: str,
    placement: str,
    scenario: ScenarioSpec,
    caption_original: str,
    existing: dict[int, dict[str, Any]] | None = None,
    on_reaction: Callable[[int, dict[str, Any]], Awaitable[None]] | None = None,
    should_cancel: Callable[[], Awaitable[bool]] | None = None,
    batch_size: int = 32,
) -> tuple[list[dict[str, Any] | None], str, dict[int, int]]:
    """Virtual agents run in the core engine: deterministic, seeded, zero LLM tokens."""
    reactions: list[dict[str, Any] | None] = [None] * table.k
    for idx, r in (existing or {}).items():
        if 0 <= idx < table.k:
            reactions[idx] = r
    scen = scenario.to_dict() | {"description": scenario.description}
    ad_dict = ad.to_dict()
    for idx in range(table.k):
        if reactions[idx] is not None:
            continue
        if should_cancel is not None and idx % batch_size == 0 and await should_cancel():
            break
        reactions[idx] = _clean_reaction(
            heuristic_reaction(
                table.profiles[idx],
                ad_dict,
                scen,
                platform_code,
                cfg.test.post_type,
                seed_salt=f"{cfg.test.test_id}:{platform_code}:{placement}",
                category=cfg.category,
            )
        )
        if on_reaction is not None:
            await on_reaction(idx, reactions[idx])
    return reactions, "engine-v1", {}


def _clean_reaction(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    out["attention"] = float(min(1.0, max(0.0, float(out.get("attention", 0.3)))))
    out["sentiment"] = float(min(1.0, max(-1.0, float(out.get("sentiment", 0.0)))))
    c = out.get("comment")
    out["comment"] = (" ".join(str(c).split()[:30])) if c else None
    if not out["comment"]:
        out["comment_topic"] = None
    out["first_impression"] = " ".join(str(out.get("first_impression", "")).split()[:25])
    out["reason"] = " ".join(str(out.get("reason", "")).split()[:40])
    return out


def variety_alert(reactions: list[dict[str, Any] | None], threshold: float = 0.6) -> dict[str, Any] | None:
    share = positive_share(reactions)
    if share > threshold:
        return {
            "code": "too_positive",
            "positive_share": round(share, 3),
            "threshold": threshold,
            "message": f"{share:.0%} of archetypes reacted positively (above {threshold:.0%}); results flagged for review",
        }
    return None


# --------------------------------------------------------------------------- comment topics


async def classify_comments(
    client: LLMClient, comments: list[str], batch_size: int = 50
) -> list[dict[str, Any]]:
    """Batched classification; returns [{index, topic, sentiment}] aligned to the input list."""
    results: list[dict[str, Any]] = [
        {"index": i, "topic": "other", "sentiment": 0.0} for i in range(len(comments))
    ]
    for start in range(0, len(comments), batch_size):
        batch = comments[start : start + batch_size]
        listing = "\n".join(f"{i}: <comment>{c}</comment>" for i, c in enumerate(batch))
        text, version = prompts.render("comment_topics", comments=listing)
        try:
            data = await client.complete_json(
                stage="classify",
                kind="agent",
                system="You label short social media comments and return strict JSON.",
                user=text,
                schema_name="comment_topics",
                schema=SCHEMAS["comment_topics"],
                temperature=0.0,
                context={"comments": batch},
                prompt_version=version,
            )
        except InvalidJSONError:
            continue
        for lab in data.get("labels") or []:
            try:
                i = int(lab["index"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= i < len(batch):
                results[start + i] = {
                    "index": start + i,
                    "topic": str(lab.get("topic", "other")),
                    "sentiment": float(lab.get("sentiment", 0.0)),
                }
    return results


# --------------------------------------------------------------------------- reasons
REASON_STYLE = (
    "\n\nWriting rules for EVERY statement (these override anything above about wording):\n"
    "- One plain sentence, at most 18 words, for a small-business owner with no technical background.\n"
    '- Say "people". Never say "agents", "virtual agents", "P10", "P50", "P90" or "median across runs".\n'
    "- Write ONE statement per topic that covers all platforms and cite all of that topic's evidence ids.\n"
    "- Do not list per-platform numbers in the statement. Say what is true across platforms "
    '(e.g. "on every platform", "Facebook and TikTok reached the most people"). '
    "The numbers are shown separately on cards, so use at most one number.\n"
)


def _platform_label(code: str) -> str:
    return {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok"}.get(
        str(code).lower(), str(code).capitalize()
    )


def _short_statement(ev: dict[str, Any]) -> str:
    """Plain one-platform sentence for an evidence item."""
    v = ev.get("values") or {}
    p = _platform_label(ev.get("platform") or "")
    if ev.get("type") == "timing" and isinstance(v.get("first_24h_reach_share"), (int, float)):
        s = v["first_24h_reach_share"]
        pct = round(s * 100) if s <= 1 else round(s)
        return f"On {p}, {pct}% of the people reached saw the ad in the first 24 hours."
    if ev.get("type") == "headline" and isinstance(v.get("seen"), (int, float)):
        return f"On {p}, {int(v['seen'])} people saw the ad."
    return ev["statement"]


def split_multi_platform(
    reasons: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A reason that cites evidence from several platforms becomes one reason per platform."""
    by_id = {e["id"]: e for e in evidence}
    out: list[dict[str, Any]] = []
    for r in reasons:
        items = [by_id[i] for i in r["evidence_ids"] if i in by_id]
        plats = {e.get("platform") for e in items if e.get("platform")}
        if len(plats) <= 1:
            out.append(r)
            continue
        shared = [e["id"] for e in items if not e.get("platform")]
        want = "headline" if r["section"] == "reach" else r["section"]
        for plat in sorted(plats):
            mine = [e for e in items if e.get("platform") == plat]
            main = next((e for e in mine if e["type"] == want), mine[0])
            out.append(
                {
                    **r,
                    "statement": _short_statement(main),
                    "evidence_ids": [main["id"]] + [e["id"] for e in mine if e is not main] + shared,
                }
            )
    return out


async def write_reasons(
    client: LLMClient,
    cfg: FrozenConfig,
    evidence: list[dict[str, Any]],
    example_comments: list[str],
    goal_metric: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Reasons from evidence only. Rejected statements are regenerated once, then dropped."""
    table = "\n".join(f"{e['id']} [{e['type']}] {e['statement']}" for e in evidence)
    text, version = prompts.render(
        "reasons",
        goal=cfg.test.goal,
        goal_metric=goal_metric,
        post_type=cfg.test.post_type,
        profile_summary=profile_summary(cfg.profile, cfg.category),
        evidence_table=table,
        example_comments="\n".join(f"- {c}" for c in example_comments[:20]) or "(none)",
    )
    text = text + REASON_STYLE
    context = {"evidence": evidence, "goal": cfg.test.goal}
    try:
        data = await client.complete_json(
            stage="explain",
            kind="smart",
            system="You write factual, evidence-based report statements and return strict JSON.",
            user=text,
            schema_name="reasons",
            schema=SCHEMAS["reasons"],
            temperature=0.3,
            context=context,
            prompt_version=version,
        )
    except InvalidJSONError:
        data = {"reasons": []}
    accepted, rejected = validate_reasons(data.get("reasons") or [], evidence)
    if rejected:
        retry_text = (
            text
            + "\n\nThe following statements were rejected ("
            + "; ".join(",".join(r.get("problems", [])) for r in rejected)
            + "). Rewrite ONLY these without the problems:\n"
            + "\n".join(f"- {r['statement']}" for r in rejected)
        )
        try:
            data2 = await client.complete_json(
                stage="explain",
                kind="smart",
                system="You write factual, evidence-based report statements and return strict JSON.",
                user=retry_text,
                schema_name="reasons",
                schema=SCHEMAS["reasons"],
                temperature=0.2,
                context=context | {"retry": True},
                prompt_version=version,
            )
            acc2, rej2 = validate_reasons(data2.get("reasons") or [], evidence)
            accepted.extend(acc2)
            rejected = rej2
        except InvalidJSONError:
            rejected = [{**r, "problems": r.get("problems", []) + ["retry_invalid_json"]} for r in rejected]
    # split any reason that spans several platforms into one reason per platform
    # accepted = split_multi_platform(accepted, evidence)
    # de-duplicate by statement
    seen: set[str] = set()
    unique = []
    for r in accepted:
        key = r["statement"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique[:14], rejected, version

# --------------------------------------------------------------------------- category draft


async def draft_category(
    client: LLMClient, *, name: str, code: str | None, parent_code: str | None, hints: str
) -> dict[str, Any]:
    text, version = prompts.render(
        "category_draft", name=name, code=code or "", parent_code=parent_code or "none", hints=hints or "none"
    )
    data = await client.complete_json(
        stage="category_draft",
        kind="smart",
        system="You design structured business-category templates and return strict JSON.",
        user=text,
        schema_name="category_draft",
        schema=SCHEMAS["category_draft"],
        temperature=0.4,
        context={"name": name, "code": code, "parent_code": parent_code, "hints": hints},
        prompt_version=version,
    )
    return template_from_draft(data)


def template_from_draft(d: dict[str, Any]) -> dict[str, Any]:
    """Convert the LLM draft shape into the category_templates row shape."""
    dims = [str(x) for x in (d.get("taste_dimensions") or ["practical", "emotional", "status", "fun"])][:4]
    questions = []
    for q in d.get("questions") or []:
        q2 = {"key": q["key"], "label": q["label"], "type": q["type"], "required": bool(q.get("required"))}
        if q.get("options"):
            q2["options"] = list(q["options"])
        if q["type"] == "sliders":
            q2["options"] = dims
            q2["min"], q2["max"] = 0, 1
            q2["default"] = dict.fromkeys(dims, 0.5)
        if q.get("feeds_trait"):
            q2["feeds_trait"] = q["feeds_trait"]
        if q.get("help"):
            q2["help"] = q["help"]
        if q["type"] == "number":
            q2["min"] = 0
        questions.append(q2)
    mixes = {}
    for m in d.get("customer_mixes") or []:
        total = (
            sum(
                float(m.get(k, 0))
                for k in ("grew_up_with_it", "tried_elsewhere", "foreigner_likes_it", "never_tried")
            )
            or 1.0
        )
        mixes[str(m["name"])] = {
            k: round(float(m.get(k, 0)) / total, 3)
            for k in ("grew_up_with_it", "tried_elsewhere", "foreigner_likes_it", "never_tried")
        }
    if not mixes:
        mixes = {
            "mixed": {
                "grew_up_with_it": 0.4,
                "tried_elsewhere": 0.3,
                "foreigner_likes_it": 0.1,
                "never_tried": 0.2,
            }
        }
    for q in questions:
        if q.get("feeds_trait") == "familiarity" and q["type"] == "select":
            q["options"] = list(mixes.keys())
    return {
        "code": str(d.get("code")),
        "name": str(d.get("name")),
        "parent_code": d.get("parent_code"),
        "tags": [str(t) for t in (d.get("tags") or [])],
        "questions": questions,
        "trait_dimensions": [
            {
                "key": "taste",
                "label": "Preferences",
                "kind": "vector",
                "values": dims,
                "default_distribution": {x: {"mean": 0.5, "sd": 0.2} for x in dims},
                "familiarity_shift": {
                    "grew_up_with_it": 0.05,
                    "tried_elsewhere": 0.0,
                    "foreigner_likes_it": 0.0,
                    "never_tried": -0.1,
                },
            },
            {
                "key": "familiarity",
                "label": "Familiarity",
                "kind": "categorical",
                "values": ["grew_up_with_it", "tried_elsewhere", "foreigner_likes_it", "never_tried"],
                "from_question": "customer_mix",
            },
            {
                "key": "brand_relationship",
                "label": "Brand relationship",
                "kind": "reputation",
                "values": ["unaware", "aware_not_tried", "tried_liked", "tried_disliked", "regular"],
            },
        ],
        "activation_rules": [
            {"ad_feature": "price_shown", "trait": "price_sensitivity", "weight": 0.6},
            {"ad_feature": "trust_signals", "trait": "skepticism", "weight": 0.7},
            {"ad_feature": "hook_strength", "trait": "patience", "weight": 0.9},
        ],
        "default_mixes": mixes,
        "buying_behavior": dict(d.get("buying_behavior") or {}),
        "blockers": list(d.get("blockers") or []),
        "trust_signals": list(d.get("trust_signals") or []),
        "comment_topics": ["price", "product_detail", "service", "positive", "negative", "other"],
        "typical_goals": [str(g) for g in (d.get("typical_goals") or ["awareness"])],
        "analyzer_hints": {
            "look_for": [str(x) for x in (d.get("analyzer_look_for") or [])],
            "taste_dimensions": dims,
            "interest_tags": [str(t) for t in (d.get("tags") or [])],
        },
        "benchmark_adjustments": {
            str(b["metric"]): float(b["multiplier"])
            for b in (d.get("benchmark_adjustments") or [])
            if "metric" in b
        },
        "calendar": {},
        "restrictions": {f"note_{i + 1}": str(r) for i, r in enumerate(d.get("restrictions") or [])},
        "country_overrides": {},
    }
