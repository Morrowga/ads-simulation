"""Admin app settings (limits, Myanmar payment accounts, social links, trial switch) and the
generic publish / rollback endpoints for every versioned settings kind."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, AdminUser, Client
from app.errors import ApiError, ErrorCode
from app.schemas.admin import AppSettingsIn, AppSettingsOut, PublishIn, RollbackIn
from app.schemas.config import SettingsVersionOut
from app.services import audit, settings_service, settings_versions

router = APIRouter(prefix="/settings", tags=["admin"])

EDITABLE_KEYS = {
    "trial_enabled",
    "trial_tier",
    "trial_ip_limit_per_day",
    "trial_device_limit_per_day",
    "score_weights_by_goal",
    "rate_limits",
    "cancel_policy",
    "banned_words",
    "limits",
    "manual_payment",
    "social_links",
    "report_note",
    "brand_constants",
    "friend_graph_k",
    "analyzer_look_for",
}


@router.get("", response_model=AppSettingsOut)
async def get_settings_values(db: DB, admin: AdminUser) -> AppSettingsOut:
    values = await settings_service.get_all(db, use_cache=False)
    return AppSettingsOut(values=values, updated_at=await settings_service.last_updated(db))


@router.put("", response_model=AppSettingsOut)
async def put_settings_values(
    body: AppSettingsIn, db: DB, admin: AdminUser, client: Client
) -> AppSettingsOut:
    unknown = [k for k in body.values if k not in EDITABLE_KEYS]
    if unknown:
        raise ApiError(
            ErrorCode.validation_error,
            "Unknown settings keys",
            details={"unknown": unknown, "allowed": sorted(EDITABLE_KEYS)},
        )
    values = await settings_service.set_many(db, body.values)
    await audit.log(
        db,
        actor_id=admin.id,
        action="admin.settings.update",
        entity="settings",
        entity_id="app",
        data={"keys": list(body.values.keys()), "change_note": body.change_note},
        ip=client.ip,
    )
    return AppSettingsOut(values=values, updated_at=await settings_service.last_updated(db))


@router.post("/{kind}/{version_id}/publish", response_model=SettingsVersionOut)
async def publish_version(
    kind: str, version_id: str, db: DB, admin: AdminUser, client: Client, body: PublishIn | None = None
) -> SettingsVersionOut:
    return SettingsVersionOut(
        **await settings_versions.publish(
            db, kind, version_id, body.change_note if body else "", admin.id, client.ip
        )
    )


@router.post("/{kind}/{version_id}/rollback", response_model=SettingsVersionOut)
async def rollback_version(
    kind: str, version_id: str, db: DB, admin: AdminUser, client: Client, body: RollbackIn | None = None
) -> SettingsVersionOut:
    return SettingsVersionOut(
        **await settings_versions.rollback(
            db,
            kind,
            version_id,
            body.to_version if body else None,
            body.change_note if body else "",
            admin.id,
            client.ip,
        )
    )
