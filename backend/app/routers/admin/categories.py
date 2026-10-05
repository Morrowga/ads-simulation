"""Admin categories: versions, drafts, AI draft."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import DB, AdminUser, Client
from app.errors import ApiError, ErrorCode
from app.schemas.admin import CategoryDraftAiIn, VersionedCreateIn, VersionedUpdateIn
from app.schemas.config import SettingsVersionOut
from app.services import category_ai_draft, settings_versions

router = APIRouter(prefix="/categories", tags=["admin"])


@router.get("", response_model=list[SettingsVersionOut])
async def list_categories(
    db: DB, admin: AdminUser, with_data: bool = Query(default=False)
) -> list[SettingsVersionOut]:
    return [
        SettingsVersionOut(**v)
        for v in await settings_versions.list_versions(db, "categories", None, with_data)
    ]


@router.post("", response_model=SettingsVersionOut, status_code=201)
async def create_category_draft(
    body: VersionedCreateIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    return SettingsVersionOut(
        **await settings_versions.create_draft(db, "categories", body.model_dump(), admin.id, client.ip)
    )


@router.post("/draft-ai", response_model=SettingsVersionOut, status_code=201)
async def draft_category_ai(
    body: CategoryDraftAiIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    out = await category_ai_draft.draft_with_ai(
        db,
        name=body.name,
        code=body.code,
        parent_code=body.parent_code,
        hints=body.hints,
        actor_id=admin.id,
        ip=client.ip,
    )
    return SettingsVersionOut(**{k: v for k, v in out.items() if k in SettingsVersionOut.model_fields})


@router.get("/{code}", response_model=list[SettingsVersionOut])
async def category_versions(code: str, db: DB, admin: AdminUser) -> list[SettingsVersionOut]:
    rows = await settings_versions.list_versions(db, "categories", code, with_data=True)
    if not rows:
        raise ApiError(ErrorCode.not_found, "Category not found")
    return [SettingsVersionOut(**v) for v in rows]


@router.put("/{code}", response_model=SettingsVersionOut)
async def update_category(
    code: str, body: VersionedUpdateIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    versions = await settings_versions.list_versions(db, "categories", code)
    draft = next((v for v in versions if v["status"] == "draft"), None)
    payload = {"name": body.name, "data": body.data, "change_note": body.change_note}
    if draft is not None:
        return SettingsVersionOut(
            **await settings_versions.update_version(
                db, "categories", draft["id"], payload, admin.id, client.ip
            )
        )
    if not versions:
        raise ApiError(ErrorCode.not_found, "Category not found; create it with POST")
    return SettingsVersionOut(
        **await settings_versions.create_draft(
            db, "categories", {"code": code, **payload}, admin.id, client.ip
        )
    )
