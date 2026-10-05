"""Strict JSON schemas for structured outputs (every property required, no additional properties)."""

from __future__ import annotations

from typing import Any

ACTIONS = ["skip", "pause", "react", "comment", "click", "message", "buy", "share", "save"]
TOPICS = ["price", "product_detail", "service", "positive", "negative", "other"]
BLOCKERS = ["price", "shipping", "size", "trust", "relevance", "none"]

REACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "attention": {"type": "number", "description": "0-1 how likely this person stops scrolling"},
        "first_impression": {"type": "string", "description": "max 25 words, English"},
        "image_impressed": {"type": "boolean"},
        "caption_read": {"type": "boolean"},
        "sentiment": {"type": "number", "description": "-1.0 to 1.0"},
        "likely_action": {"type": "string", "enum": ACTIONS},
        "comment": {"type": ["string", "null"], "description": "English, max 30 words, or null"},
        "comment_topic": {"type": ["string", "null"], "enum": TOPICS + [None]},
        "purchase_blockers": {"type": "array", "items": {"type": "string", "enum": BLOCKERS}},
        "reason": {"type": "string", "description": "max 40 words, English"},
    },
    "required": [
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
    ],
}

AD_ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "description": {
            "type": "string",
            "description": "Neutral English description of what is shown, max 80 words",
        },
        "caption_language": {
            "type": "string",
            "description": "ISO 639-1 code of the caption language, e.g. th, my, en",
        },
        "caption_english": {
            "type": "string",
            "description": "English translation of the caption (or the caption itself if English)",
        },
        "first_glance": {
            "type": "string",
            "description": "What a person sees in the first second, max 20 words, no judgement",
        },
        "generic_signals": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "menu_or_price_list",
                    "stock_photo",
                    "text_only",
                    "template_layout",
                    "cluttered_text",
                    "low_resolution",
                    "no_clear_product",
                    "no_people_or_emotion",
                    "none",
                ],
            },
            "description": "Generic or weak signals actually visible; use [\"none\"] if there are none",
        },
        "hook_strength": {
            "type": "number",
            "description": "0-1 strength of the first 1-2 seconds / first glance; average ad = 0.5, 0.85+ is rare",
        },
        "novelty": {
            "type": "number",
            "description": "0-1, 0 = seen a hundred times, 1 = genuinely surprising",
        },
        "genericness": {
            "type": "number",
            "description": "0-1, 1 = template/stock/menu-style content that could be any business's",
        },
        "offer_visible_at_s": {
            "type": ["number", "null"],
            "description": "seconds until the offer/price/discount is visible; null if never",
        },
        "key_moments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"t": {"type": "number"}, "label": {"type": "string"}},
                "required": ["t", "label"],
            },
        },
        "category": {"type": "string", "description": "product category shown, e.g. food, fashion, beauty"},
        "on_screen_text": {"type": "string"},
        "sound_reliance": {"type": "number", "description": "0-1 how much the message depends on audio"},
        "price_shown": {"type": "boolean"},
        "price_level": {"type": "number", "description": "0 cheap - 1 expensive relative to the category"},
        "discount_pct": {"type": "number", "description": "discount percentage shown, 0 if none"},
        "trust_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "e.g. reviews, price_shown, location_shown, photos_of_real_food, free_shipping, guarantee",
        },
        "cta": {
            "type": "string",
            "description": "learn_more|shop_now|send_message|order_now|sign_up|book_now|get_offer|none",
        },
        "caption_strength": {"type": "number", "description": "0-1 how much the caption adds"},
        "taste_profile": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "dims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"name": {"type": "string"}, "value": {"type": "number"}},
                        "required": ["name", "value"],
                    },
                }
            },
            "required": ["dims"],
        },
        "interest_tags": {"type": "array", "items": {"type": "string"}},
        "visual_quality": {"type": "number", "description": "0-1 production quality only"},
        "clarity": {"type": "number", "description": "0-1 how clear the offer / message is within 2 seconds"},
        "emotional_tone": {
            "type": "string",
            "description": "neutral|funny|warm|formal|urgent|hard_sell|emotional",
        },
    },
    "required": [
        "description",
        "caption_language",
        "caption_english",
        "first_glance",
        "generic_signals",
        "hook_strength",
        "novelty",
        "genericness",
        "offer_visible_at_s",
        "key_moments",
        "category",
        "on_screen_text",
        "sound_reliance",
        "price_shown",
        "price_level",
        "discount_pct",
        "trust_signals",
        "cta",
        "caption_strength",
        "taste_profile",
        "interest_tags",
        "visual_quality",
        "clarity",
        "emotional_tone",
    ],
}

TOPIC_CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "index": {"type": "integer"},
                    "topic": {"type": "string", "enum": TOPICS},
                    "sentiment": {"type": "number"},
                },
                "required": ["index", "topic", "sentiment"],
            },
        }
    },
    "required": ["labels"],
}

REASONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reasons": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "attention|dropoff|blockers|segments|brand|taste|timing|comments|language|reach",
                    },
                    "statement": {
                        "type": "string",
                        "description": "one factual sentence in English, numbers only from the evidence",
                    },
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["section", "statement", "evidence_ids", "confidence"],
            },
        }
    },
    "required": ["reasons"],
}

CATEGORY_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "code": {"type": "string"},
        "name": {"type": "string"},
        "parent_code": {"type": ["string", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["text", "number", "select", "multiselect", "boolean", "sliders"],
                    },
                    "options": {"type": "array", "items": {"type": "string"}},
                    "required": {"type": "boolean"},
                    "feeds_trait": {"type": ["string", "null"]},
                    "help": {"type": ["string", "null"]},
                },
                "required": ["key", "label", "type", "options", "required", "feeds_trait", "help"],
            },
        },
        "taste_dimensions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-4 taste/preference dimensions for the vector trait",
        },
        "customer_mixes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "grew_up_with_it": {"type": "number"},
                    "tried_elsewhere": {"type": "number"},
                    "foreigner_likes_it": {"type": "number"},
                    "never_tried": {"type": "number"},
                },
                "required": [
                    "name",
                    "grew_up_with_it",
                    "tried_elsewhere",
                    "foreigner_likes_it",
                    "never_tried",
                ],
            },
        },
        "buying_behavior": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "impulse_share": {"type": "number"},
                "repeat_rate": {"type": "number"},
                "price_sensitivity": {"type": "number"},
                "decision_time_h": {"type": "number"},
            },
            "required": ["impulse_share", "repeat_rate", "price_sensitivity", "decision_time_h"],
        },
        "blockers": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": {"type": "string", "enum": BLOCKERS[:5]},
                    "label": {"type": "string"},
                    "weight": {"type": "number"},
                },
                "required": ["code", "label", "weight"],
            },
        },
        "trust_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": {"type": "string"},
                    "label": {"type": "string"},
                    "weight": {"type": "number"},
                },
                "required": ["code", "label", "weight"],
            },
        },
        "typical_goals": {
            "type": "array",
            "items": {"type": "string", "enum": ["sales", "messages", "traffic", "awareness", "engagement"]},
        },
        "analyzer_look_for": {"type": "array", "items": {"type": "string"}},
        "benchmark_adjustments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"metric": {"type": "string"}, "multiplier": {"type": "number"}},
                "required": ["metric", "multiplier"],
            },
        },
        "restrictions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "code",
        "name",
        "parent_code",
        "tags",
        "questions",
        "taste_dimensions",
        "customer_mixes",
        "buying_behavior",
        "blockers",
        "trust_signals",
        "typical_goals",
        "analyzer_look_for",
        "benchmark_adjustments",
        "restrictions",
    ],
}

SCHEMAS = {
    "reaction": REACTION_SCHEMA,
    "ad_analysis": AD_ANALYSIS_SCHEMA,
    "comment_topics": TOPIC_CLASSIFY_SCHEMA,
    "reasons": REASONS_SCHEMA,
    "category_draft": CATEGORY_DRAFT_SCHEMA,
}
