"""Admin platforms: status full/beta/planned and versioned settings (new version per save)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB, AdminUser, Client
from app.errors import ApiError, ErrorCode
from app.models import Platform
from app.schemas.admin import PlatformAdminOut, PlatformUpsertIn
from app.schemas.config import SettingsVersionOut
from app.services import audit, settings_versions

router = APIRouter(prefix="/platforms", tags=["admin"])


async def _out(db: DB, p: Platform) -> dict[str, Any]:
    versions = await settings_versions.list_versions(db, "platforms", p.code)
    return {
        "code": p.code,
        "name": p.name,
        "status": p.status,
        "active": p.active,
        "current_version": p.current_version,
        "versions": [{k: v for k, v in ver.items() if k != "data"} for ver in versions],
    }


@router.get("", response_model=list[PlatformAdminOut])
async def list_platforms(db: DB, admin: AdminUser) -> list[PlatformAdminOut]:
    rows = (await db.execute(select(Platform).order_by(Platform.sort_order, Platform.code))).scalars().all()
    return [PlatformAdminOut(**await _out(db, p)) for p in rows]


@router.get("/{code}", response_model=PlatformAdminOut)
async def get_platform(code: str, db: DB, admin: AdminUser) -> PlatformAdminOut:
    p = await db.get(Platform, code)
    if p is None:
        raise ApiError(ErrorCode.not_found, "Platform not found")
    return PlatformAdminOut(**await _out(db, p))


@router.get("/{code}/versions", response_model=list[SettingsVersionOut])
async def platform_versions(code: str, db: DB, admin: AdminUser) -> list[SettingsVersionOut]:
    return [
        SettingsVersionOut(**v)
        for v in await settings_versions.list_versions(db, "platforms", code, with_data=True)
    ]


@router.put("/{code}", response_model=PlatformAdminOut)
async def put_platform(
    code: str, body: PlatformUpsertIn, db: DB, admin: AdminUser, client: Client
) -> PlatformAdminOut:
    """Status/name/active change immediately (audited); settings changes create a new draft version."""
    p = await db.get(Platform, code)
    changes: dict[str, Any] = {}
    if p is None:
        p = Platform(
            code=code,
            name=body.name or code.title(),
            status=body.status or "planned",
            active=body.active if body.active is not None else True,
        )
        db.add(p)
        changes["created"] = True
    else:
        if body.name:
            p.name = body.name
            changes["name"] = body.name
        if body.status:
            p.status = body.status
            changes["status"] = body.status
        if body.active is not None:
            p.active = body.active
            changes["active"] = body.active
    await db.flush()
    if body.global_config is not None or body.markets is not None or body.sources is not None:
        published = None
        try:
            published = await settings_versions.published_platform(db, code)
        except ApiError:
            published = None
        data = {
            "global": body.global_config
            if body.global_config is not None
            else (published or {}).get("global", {}),
            "markets": body.markets if body.markets is not None else (published or {}).get("markets", {}),
            "sources": body.sources if body.sources is not None else (published or {}).get("sources", {}),
        }
        versions = await settings_versions.list_versions(db, "platforms", code)
        draft = next((v for v in versions if v["status"] == "draft"), None)
        if draft is not None:
            ver = await settings_versions.update_version(
                db,
                "platforms",
                draft["id"],
                {"data": data, "change_note": body.change_note},
                admin.id,
                client.ip,
            )
        else:
            ver = await settings_versions.create_draft(
                db,
                "platforms",
                {"code": code, "data": data, "change_note": body.change_note},
                admin.id,
                client.ip,
            )
        changes["draft_version"] = ver["version"]
    if changes:
        await audit.log(
            db,
            actor_id=admin.id,
            action="admin.platform.update",
            entity="platform",
            entity_id=code,
            data=changes,
            ip=client.ip,
        )
    return PlatformAdminOut(**await _out(db, p))
