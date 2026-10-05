"""Duplicate fingerprint (Backend document 6.5): canonical JSON of everything that changes a result."""

from __future__ import annotations

import json
import re
from typing import Any

from app.models import AdAsset, AdTest
from app.security import sha256_hex


def normalise_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def sha256_json(payload: Any) -> str:
    return sha256_hex(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


def build_payload(test: AdTest, assets: list[AdAsset], engine_version: str) -> dict[str, Any]:
    profile = dict(test.profile_snapshot or {})
    profile = {k: v for k, v in profile.items() if not k.startswith("_")}
    copy = test.ad_copy or {}
    return {
        "media": sorted(a.sha256 for a in assets if a.kind in ("image", "video")),
        "copy": normalise_text(copy.get("caption"))
        + "|"
        + normalise_text(copy.get("headline"))
        + "|"
        + normalise_text(copy.get("cta")),
        "platforms": sorted(
            [
                [
                    x.get("code"),
                    sorted(x.get("placements") or []),
                    float(x.get("budget_share") or 0),
                    x.get("settings_version"),
                ]
                for x in (test.platforms or [])
            ],
            key=lambda p: str(p[0]),
        ),
        "post": [test.post_type, test.goal],
        "schedule": test.schedule or {},
        "budget": [test.budget_minor, test.currency],
        "audiences": test.audiences or [],
        "country": test.country_code,
        "tier": test.tier_code,
        "settings": test.settings_versions or {},
        "profile": sha256_json(profile),
        "engine": engine_version,
    }


def fingerprint(test: AdTest, assets: list[AdAsset], engine_version: str) -> tuple[str, dict[str, Any]]:
    payload = build_payload(test, assets, engine_version)
    return sha256_json(payload), payload


FIELD_LABELS = {
    "media": "media",
    "copy": "caption / headline / CTA",
    "platforms": "platforms or budget split",
    "post": "post type or goal",
    "schedule": "schedule",
    "budget": "budget",
    "audiences": "audiences",
    "country": "country",
    "tier": "tier",
    "settings": "engine settings versions",
    "profile": "business profile",
    "engine": "engine version",
}


def changed_fields(a: dict[str, Any] | None, b: dict[str, Any] | None) -> list[str]:
    if not a or not b:
        return []
    out = []
    for key, label in FIELD_LABELS.items():
        if json.dumps(a.get(key), sort_keys=True, default=str) != json.dumps(
            b.get(key), sort_keys=True, default=str
        ):
            out.append(label)
    return out
