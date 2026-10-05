"""GET /platforms: status, placements, ad specs, post types and supported goals from the published version."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB
from app.models import Platform, PlatformSettings
from app.schemas.config import PlacementOut, PlatformOut, PostTypeSupportOut
from engine.simulation.config.resolver import strip_sources

router = APIRouter(tags=["config"])


def platform_out(platform: Platform, ver: PlatformSettings | None) -> dict[str, Any]:
    g = strip_sources(ver.global_config) if ver else {}
    raw_placements = (ver.global_config if ver else {}).get("placements", {}) or {}
    placements = []
    ad_specs: dict[str, Any] = {}
    for code, spec in raw_placements.items():
        spec = spec or {}
        placements.append(
            PlacementOut(
                code=code,
                formats=[str(f) for f in spec.get("formats", [])],
                ratios=[str(r) for r in spec.get("ratios", [])],
                video_s=[float(x) for x in spec.get("video_s", [])] or None,
                max_caption_chars=spec.get("max_caption_chars"),
                source=spec.get("source"),
            )
        )
        ad_specs[code] = spec
    supported = {k: list(v) for k, v in (g.get("supported_goals") or {}).items()}
    return {
        "code": platform.code,
        "name": platform.name,
        "status": platform.status,
        "version": ver.version if ver else None,
        "placements": placements,
        "ad_specs": ad_specs,
        "post_types": [
            PostTypeSupportOut(post_type=pt, supported_goals=goals) for pt, goals in supported.items()
        ],
        "supported_goals": supported,
        "actions": [str(a) for a in g.get("actions", [])],
        "organic": g.get("organic", {}) or {},
    }


@router.get("/platforms", response_model=list[PlatformOut])
async def list_platforms(db: DB) -> list[PlatformOut]:
    rows = (
        (
            await db.execute(
                select(Platform).where(Platform.active.is_(True)).order_by(Platform.sort_order, Platform.code)
            )
        )
        .scalars()
        .all()
    )
    out = []
    for p in rows:
        ver = (
            (
                await db.execute(
                    select(PlatformSettings)
                    .where(PlatformSettings.platform_code == p.code, PlatformSettings.status == "published")
                    .order_by(PlatformSettings.version.desc())
                )
            )
            .scalars()
            .first()
        )
        out.append(PlatformOut(**platform_out(p, ver)))
    return out
