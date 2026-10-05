"""Admin weights: behaviour and score weights (versioned)."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, AdminUser, Client
from app.schemas.admin import WeightsIn, WeightsOut
from app.services import settings_versions

router = APIRouter(prefix="/weights", tags=["admin"])


async def _out(db: DB) -> WeightsOut:
    versions = await settings_versions.list_versions(db, "weights", None, with_data=True)
    current = next((v for v in versions if v["status"] == "published"), versions[0] if versions else None)
    if current is None:
        return WeightsOut(
            version=0, status="none", behavior={}, score_by_goal={}, change_note="", versions=[]
        )
    data = current["data"] or {}
    return WeightsOut(
        version=current["version"],
        status=current["status"],
        behavior=data.get("behavior", {}),
        score_by_goal=data.get("score_by_goal", {}),
        change_note=current["change_note"],
        versions=[{k: v for k, v in ver.items() if k != "data"} for ver in versions],
    )


@router.get("", response_model=WeightsOut)
async def get_weights(db: DB, admin: AdminUser) -> WeightsOut:
    return await _out(db)


@router.put("", response_model=WeightsOut)
async def put_weights(body: WeightsIn, db: DB, admin: AdminUser, client: Client) -> WeightsOut:
    versions = await settings_versions.list_versions(db, "weights", None)
    draft = next((v for v in versions if v["status"] == "draft"), None)
    payload = {
        "data": {"behavior": body.behavior, "score_by_goal": body.score_by_goal},
        "change_note": body.change_note,
    }
    if draft is not None:
        ver = await settings_versions.update_version(db, "weights", draft["id"], payload, admin.id, client.ip)
    else:
        ver = await settings_versions.create_draft(db, "weights", payload, admin.id, client.ip)
    if body.publish:
        await settings_versions.publish(db, "weights", ver["id"], body.change_note, admin.id, client.ip)
    return await _out(db)
