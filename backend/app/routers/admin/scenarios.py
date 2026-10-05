"""Admin scenarios: versions, drafts, edits."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import DB, AdminUser, Client
from app.schemas.admin import VersionedCreateIn, VersionedUpdateIn
from app.schemas.config import ScenarioOut, SettingsVersionOut
from app.services import settings_versions

router = APIRouter(prefix="/scenarios", tags=["admin"])


def _scenario_out(v: dict) -> ScenarioOut:  # noqa: ANN001
    d = v.get("data") or {}
    return ScenarioOut(
        id=v["id"],
        code=v["code"],
        name=d.get("name", v["code"]),
        version=v["version"],
        modifiers=d.get("modifiers", {}),
        country_codes=d.get("country_codes", []),
        category_codes=d.get("category_codes", []),
        date_rules=d.get("date_rules", {}),
        weight=float(d.get("weight", 1.0)),
        active=bool(d.get("active", True)),
        status=v["status"],
        change_note=v["change_note"],
        created_by=v["created_by"],
        published_at=v["published_at"],
        created_at=v["created_at"],
    )


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    db: DB, admin: AdminUser, code: str | None = Query(default=None)
) -> list[ScenarioOut]:
    return [
        _scenario_out(v) for v in await settings_versions.list_versions(db, "scenarios", code, with_data=True)
    ]


@router.post("", response_model=SettingsVersionOut, status_code=201)
async def create_scenario(
    body: VersionedCreateIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    return SettingsVersionOut(
        **await settings_versions.create_draft(db, "scenarios", body.model_dump(), admin.id, client.ip)
    )


@router.get("/{scenario_id}", response_model=SettingsVersionOut)
async def get_scenario(scenario_id: str, db: DB, admin: AdminUser) -> SettingsVersionOut:
    row = await settings_versions._get_row(db, "scenarios", scenario_id)
    return SettingsVersionOut(
        **settings_versions._version_out("scenarios", row, row.code, settings_versions.scenario_dict(row))
    )


@router.put("/{scenario_id}", response_model=SettingsVersionOut)
async def update_scenario(
    scenario_id: str, body: VersionedUpdateIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    return SettingsVersionOut(
        **await settings_versions.update_version(
            db, "scenarios", scenario_id, body.model_dump(), admin.id, client.ip
        )
    )
