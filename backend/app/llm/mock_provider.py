"""Deterministic mock provider: realistic fake structured outputs so the whole pipeline runs without
an API key. Outputs are seeded from the prompt/context, so runs are reproducible."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from app.llm.client import ProviderResult
from engine.simulation.results.evidence import banned_word_hits
from engine.simulation.reaction.priors import heuristic_reaction

THAI = re.compile(r"[฀-๿]")
MYANMAR = re.compile(r"[က-႟]")
CJK = re.compile(r"[一-鿿]")
JAPANESE = re.compile(r"[぀-ヿ]")
KOREAN = re.compile(r"[가-힯]")
SPANISH_HINT = re.compile(r"\b(el|la|los|las|hoy|gratis|descuento|envío)\b", re.I)


def detect_language(text: str) -> str:
    if not text:
        return "en"
    if THAI.search(text):
        return "th"
    if MYANMAR.search(text):
        return "my"
    if JAPANESE.search(text):
        return "ja"
    if KOREAN.search(text):
        return "ko"
    if CJK.search(text):
        return "zh"
    if SPANISH_HINT.search(text):
        return "es"
    return "en"


def _seed(*parts: Any) -> int:
    return int.from_bytes(hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).digest()[:8], "big")


def _unit(seed: int, salt: str) -> float:
    return (_seed(seed, salt) % 10_000) / 10_000.0


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MockProvider:
    name = "mock"

    async def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema_name: str,
        schema: dict[str, Any],
        temperature: float,
        images: list[bytes] | None,
        context: dict[str, Any] | None,
    ) -> ProviderResult:
        t0 = time.perf_counter()
        ctx = context or {}
        if schema_name == "reaction":
            data = heuristic_reaction(
                ctx.get("archetype", {}),
                ctx.get("ad", {}),
                ctx.get("scenario"),
                ctx.get("platform", "facebook"),
                ctx.get("post_type", "paid"),
                seed_salt=ctx.get("salt", ""),
            )
        elif schema_name == "ad_analysis":
            data = self._ad_analysis(ctx, images or [])
        elif schema_name == "comment_topics":
            data = self._topics(ctx)
        elif schema_name == "reasons":
            data = self._reasons(ctx)
        elif schema_name == "category_draft":
            data = self._category_draft(ctx)
        else:
            data = {}
        n_in = _tokens(system) + _tokens(user) + 85 * len(images or [])
        cached = int(_tokens(system) * 0.9) if schema_name == "reaction" else 0
        return ProviderResult(
            data=data,
            text="",
            input_tokens=n_in,
            cached_tokens=cached,
            output_tokens=max(20, len(str(data)) // 4),
            latency_ms=int((time.perf_counter() - t0) * 1000) + 3,
            model="mock",
        )

    async def transcribe(self, *, model: str, audio: bytes, mime: str) -> ProviderResult:
        seed = _seed(len(audio), audio[:64])
        lines = [
            "Come and try our charcoal grilled seafood this weekend, twenty percent off.",
            "Message us to book your table, limited seats every evening.",
            "Fresh every day, cooked the way our family always did it.",
        ]
        text = " ".join(lines[: 1 + seed % 3])
        return ProviderResult(
            data={"text": text},
            text=text,
            input_tokens=max(1, len(audio) // 4000),
            output_tokens=_tokens(text),
            latency_ms=5,
            model="mock",
        )

    # ------------------------------------------------------------------ ad analysis

    def _ad_analysis(self, ctx: dict[str, Any], images: list[bytes]) -> dict[str, Any]:
        caption = str(ctx.get("caption") or "")
        headline = str(ctx.get("headline") or "")
        assets = ctx.get("assets") or []
        category = ctx.get("category") or {}
        transcript = str(ctx.get("transcript") or "")
        seed = _seed(caption, headline, [a.get("sha256") for a in assets])
        video = next((a for a in assets if a.get("kind") == "video"), None)
        duration = float(video.get("duration_s") or 8.0) if video else 3.0
        lang = detect_language(caption)
        text_all = f"{caption} {headline} {transcript}".lower()
        m = re.search(r"(\d{1,2})\s*%", text_all)
        discount = float(m.group(1)) if m else 0.0
        price_shown = bool(
            re.search(r"(\$|฿|บาท|ks|kyat|mmk|usd|thb|\d{2,5}\s?(baht|kyats?))", text_all)
            or re.search(r"\b\d{2,5}\b", text_all)
            and "price" in text_all
        )
        trust: list[str] = []
        if re.search(r"review|rating|★|stars?", text_all):
            trust.append("reviews")
        if re.search(r"free (shipping|delivery)|ส่งฟรี", text_all):
            trust.append("free_shipping")
        if re.search(r"cash on delivery|cod\b", text_all):
            trust.append("cash_on_delivery")
        if re.search(r"near|street|road|branch|สาขา|location|map", text_all):
            trust.append("location_shown")
        if price_shown or discount > 0:
            trust.append("price_shown")
        if assets:
            trust.append(
                "photos_of_real_food"
                if (category.get("code") in ("restaurant", "cafe_drinks"))
                else "photos_of_real_product"
            )
        hook = 0.35 + 0.45 * _unit(seed, "hook")
        if video:
            hook = 0.3 + 0.5 * _unit(seed, "hook_v")
        offer_at: float | None
        if discount > 0 or price_shown:
            offer_at = round(duration * (0.15 + 0.35 * _unit(seed, "offer")), 1) if video else 0.0
        else:
            offer_at = None
        dims = [
            str(d)
            for d in (
                (category.get("analyzer_hints") or {}).get("taste_dimensions")
                or ["practical", "emotional", "status", "fun"]
            )
        ]
        taste_dims = [{"name": d, "value": round(0.2 + 0.7 * _unit(seed, f"taste:{d}"), 2)} for d in dims]
        profile_taste = ctx.get("profile_taste") or {}
        for td in taste_dims:
            if td["name"] in profile_taste:
                td["value"] = round(0.7 * float(profile_taste[td["name"]]) + 0.3 * td["value"], 2)
        cta = str(ctx.get("cta") or "learn_more")
        tone = ["neutral", "warm", "funny", "urgent", "formal"][seed % 5]
        kind_word = "video" if video else "image"
        desc = f"A {kind_word} for a {category.get('name', 'business').lower()}"
        if video:
            desc += f" of {duration:.0f} seconds showing the product in the first frames, a text overlay with the offer at {offer_at if offer_at is not None else 'no point'}s and a closing frame with the call to action"
        else:
            desc += " showing the product with a text overlay" + (
                " announcing a discount" if discount else ""
            )
        desc += f". The caption is in {lang}."
        key_moments = [{"t": 0.0, "label": "product shown"}]
        if video:
            if offer_at is not None:
                key_moments.append({"t": float(offer_at), "label": "offer text appears"})
            key_moments.append({"t": round(duration * 0.8, 1), "label": "call to action"})
        bland = len(caption.split()) <= 2 and not headline
        return {
            "description": desc[:600],
            "caption_language": lang,
            "caption_english": caption if lang == "en" else f"[translated from {lang}] {caption}",
            "first_glance": "the product on a plain background" if bland else "the product with a text overlay",
            "generic_signals": ["text_only"] if bland else ["none"],
            "novelty": round(0.15 if bland else 0.25 + 0.55 * _unit(seed, "novelty"), 2),
            "genericness": round(0.85 if bland else 0.2 + 0.55 * _unit(seed, "generic"), 2),
            "hook_strength": round(hook, 3),
            "offer_visible_at_s": offer_at,
            "key_moments": key_moments,
            "category": str((category.get("tags") or ["other"])[0]),
            "on_screen_text": headline or (caption[:60] if caption else ""),
            "sound_reliance": round(0.6 * _unit(seed, "sound"), 2) if video else 0.0,
            "price_shown": bool(price_shown),
            "price_level": round(0.3 + 0.5 * _unit(seed, "price"), 2),
            "discount_pct": discount,
            "trust_signals": sorted(set(trust)),
            "cta": cta,
            "caption_strength": round(min(1.0, 0.25 + len(caption) / 200.0), 2),
            "taste_profile": {"dims": taste_dims},
            "interest_tags": [str(t) for t in (category.get("tags") or ["other"])][:4],
            "visual_quality": round(0.45 + 0.45 * _unit(seed, "vq"), 2),
            "clarity": round(0.4 + 0.5 * _unit(seed, "clarity"), 2),
            "emotional_tone": tone,
        }

    # ------------------------------------------------------------------ comment topics

    def _topics(self, ctx: dict[str, Any]) -> dict[str, Any]:
        labels = []
        for i, c in enumerate(ctx.get("comments") or []):
            low = str(c).lower()
            if re.search(r"how much|price|expensive|discount|cheap|cost|\$|baht|kyat", low):
                topic, sent = "price", -0.1
            elif re.search(r"deliver|open|book|table|hours|sunday|service|staff|long", low):
                topic, sent = "service", 0.0
            elif re.search(r"spicy|size|portion|colour|color|where|menu|ingredient|taste|detail", low):
                topic, sent = "product_detail", 0.05
            elif re.search(r"amazing|love|good|saving|need to try|craving|great|nice|best", low):
                topic, sent = "positive", 0.6
            elif re.search(r"not|edited|worth|too many|again|bad|fake|seen this", low):
                topic, sent = "negative", -0.6
            else:
                topic, sent = "other", 0.0
            labels.append({"index": i, "topic": topic, "sentiment": sent})
        return {"labels": labels}

    # ------------------------------------------------------------------ reasons

    def _reasons(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Reasons built directly from the evidence table (no invention, no advice)."""
        evidence = ctx.get("evidence") or []
        out = []
        section_map = {
            "headline": "attention",
            "goal_range": "reach",
            "dropoff": "dropoff",
            "blockers": "blockers",
            "segment": "segments",
            "sponsored": "attention",
            "brand_relationship": "brand",
            "taste": "taste",
            "timing": "timing",
            "comment_topics": "comments",
            "language": "language",
            "organic_reach": "reach",
        }
        ranked = sorted(evidence, key=lambda e: -float(e.get("importance", 0.5)))
        seen_types: dict[str, int] = {}
        for e in ranked:
            etype = str(e.get("type"))
            if seen_types.get(etype, 0) >= 2:
                continue
            seen_types[etype] = seen_types.get(etype, 0) + 1
            statement = str(e.get("statement", "")).strip()
            if not statement:
                continue
            statement = statement[0].upper() + statement[1:]
            if not statement.endswith("."):
                statement += "."
            # the mock never writes instructions; guard anyway
            if banned_word_hits(statement):
                continue
            out.append(
                {
                    "section": section_map.get(etype, "general"),
                    "statement": statement,
                    "evidence_ids": [e["id"]],
                    "confidence": round(0.5 + 0.45 * float(e.get("importance", 0.5)), 2),
                }
            )
            if len(out) >= 12:
                break
        return {"reasons": out}

    # ------------------------------------------------------------------ category draft

    def _category_draft(self, ctx: dict[str, Any]) -> dict[str, Any]:
        name = str(ctx.get("name") or "New category").strip()
        code = str(ctx.get("code") or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"))
        dims = ["quality", "value", "novelty", "convenience"]
        low = name.lower()
        if any(w in low for w in ("food", "restaurant", "cafe", "bakery", "kitchen")):
            dims = ["spice", "sweet", "freshness", "adventurousness"]
        elif any(w in low for w in ("fitness", "gym", "yoga", "sport")):
            dims = ["intensity", "community", "convenience", "results"]
        elif any(w in low for w in ("school", "course", "tutor", "education", "class")):
            dims = ["practical", "prestige", "convenience", "fun"]
        questions = [
            {
                "key": "business_name",
                "label": "Business name",
                "type": "text",
                "options": [],
                "required": True,
                "feeds_trait": None,
                "help": None,
            },
            {
                "key": "what_you_sell",
                "label": "What do you sell or offer? (short description)",
                "type": "text",
                "options": [],
                "required": True,
                "feeds_trait": None,
                "help": None,
            },
            {
                "key": "price_level",
                "label": "Price level",
                "type": "select",
                "options": ["budget", "mid", "premium"],
                "required": True,
                "feeds_trait": "price_level",
                "help": None,
            },
            {
                "key": "taste_profile",
                "label": f"What your {name.lower()} is known for",
                "type": "sliders",
                "options": dims,
                "required": True,
                "feeds_trait": "taste",
                "help": "0 = not at all, 1 = very much",
            },
            {
                "key": "customer_mix",
                "label": "Who are your customers?",
                "type": "select",
                "options": ["regulars_mostly", "mixed", "new_market"],
                "required": True,
                "feeds_trait": "familiarity",
                "help": None,
            },
            {
                "key": "customer_languages",
                "label": "Languages your customers use",
                "type": "multiselect",
                "options": ["th", "en", "my", "zh", "ja", "ko", "es"],
                "required": False,
                "feeds_trait": "language_group",
                "help": None,
            },
            {
                "key": "followers",
                "label": "Followers on the platform you test",
                "type": "number",
                "options": [],
                "required": True,
                "feeds_trait": "brand_relationship",
                "help": None,
            },
            {
                "key": "review_count",
                "label": "Number of public reviews",
                "type": "number",
                "options": [],
                "required": False,
                "feeds_trait": "brand_relationship",
                "help": None,
            },
            {
                "key": "rating",
                "label": "Average rating (1-5)",
                "type": "number",
                "options": [],
                "required": False,
                "feeds_trait": "brand_relationship",
                "help": None,
            },
            {
                "key": "months_in_business",
                "label": "Months in business",
                "type": "number",
                "options": [],
                "required": False,
                "feeds_trait": "brand_relationship",
                "help": None,
            },
            {
                "key": "location_type",
                "label": "Where do customers find you?",
                "type": "select",
                "options": ["street", "mall", "online_only", "home_visit"],
                "required": False,
                "feeds_trait": None,
                "help": None,
            },
            {
                "key": "booking",
                "label": "Do customers book or order online?",
                "type": "boolean",
                "options": [],
                "required": False,
                "feeds_trait": None,
                "help": None,
            },
        ]
        return {
            "code": code,
            "name": name,
            "parent_code": ctx.get("parent_code"),
            "tags": [code, "services"],
            "questions": questions,
            "taste_dimensions": dims,
            "customer_mixes": [
                {
                    "name": "regulars_mostly",
                    "grew_up_with_it": 0.6,
                    "tried_elsewhere": 0.3,
                    "foreigner_likes_it": 0.05,
                    "never_tried": 0.05,
                },
                {
                    "name": "mixed",
                    "grew_up_with_it": 0.4,
                    "tried_elsewhere": 0.3,
                    "foreigner_likes_it": 0.1,
                    "never_tried": 0.2,
                },
                {
                    "name": "new_market",
                    "grew_up_with_it": 0.2,
                    "tried_elsewhere": 0.3,
                    "foreigner_likes_it": 0.1,
                    "never_tried": 0.4,
                },
            ],
            "buying_behavior": {
                "impulse_share": 0.45,
                "repeat_rate": 0.3,
                "price_sensitivity": 0.6,
                "decision_time_h": 24,
            },
            "blockers": [
                {"code": "price", "label": "Price", "weight": 0.3},
                {"code": "relevance", "label": "Not relevant to me", "weight": 0.25},
                {"code": "trust", "label": "Not convinced it is good", "weight": 0.25},
                {"code": "shipping", "label": "Location / logistics", "weight": 0.15},
                {"code": "size", "label": "Details unclear", "weight": 0.05},
            ],
            "trust_signals": [
                {"code": "reviews", "label": "Reviews visible", "weight": 0.85},
                {"code": "price_shown", "label": "Price shown", "weight": 0.65},
                {"code": "location_shown", "label": "Location shown", "weight": 0.55},
                {"code": "phone_number", "label": "Contact visible", "weight": 0.5},
            ],
            "typical_goals": ["messages", "awareness", "sales"],
            "analyzer_look_for": ["main offer", "price", "people", "location", "text overlay"],
            "benchmark_adjustments": [
                {"metric": "message_rate", "multiplier": 1.3},
                {"metric": "ctr", "multiplier": 1.0},
            ],
            "restrictions": ["Check local advertising rules for regulated claims."],
        }
