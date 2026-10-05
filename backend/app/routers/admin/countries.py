"""Admin countries: list with versions, create draft (new country or new version), edit draft."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB, AdminUser, Client
from app.errors import ApiError, ErrorCode
from app.models import Country
from app.schemas.admin import CountryAdminOut, CountryUpsertIn, VersionedUpdateIn
from app.schemas.config import SettingsVersionOut
from app.services import settings_versions

router = APIRouter(prefix="/countries", tags=["admin"])


async def _country_out(db: DB, c: Country) -> dict[str, Any]:
    versions = await settings_versions.list_versions(db, "countries", c.code)
    return {
        "code": c.code,
        "name": c.name,
        "currency": c.currency,
        "payment_methods": list(c.payment_methods or []),
        "active": c.active,
        "current_version": c.current_version,
        "versions": [{k: v for k, v in ver.items() if k != "data"} for ver in versions],
    }


@router.get("", response_model=list[CountryAdminOut])
async def list_countries(db: DB, admin: AdminUser) -> list[CountryAdminOut]:
    rows = (await db.execute(select(Country).order_by(Country.code))).scalars().all()
    return [CountryAdminOut(**await _country_out(db, c)) for c in rows]


@router.post("", response_model=SettingsVersionOut, status_code=201)
async def create_country_draft(
    body: CountryUpsertIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    payload = {
        "code": body.code,
        "name": body.name,
        "currency": body.currency,
        "payment_methods": body.payment_methods,
        "active": body.active,
        "data": body.data,
        "change_note": body.change_note,
    }
    return SettingsVersionOut(
        **await settings_versions.create_draft(db, "countries", payload, admin.id, client.ip)
    )


@router.get("/{code}", response_model=CountryAdminOut)
async def get_country(code: str, db: DB, admin: AdminUser) -> CountryAdminOut:
    c = await db.get(Country, code.upper())
    if c is None:
        raise ApiError(ErrorCode.not_found, "Country not found")
    return CountryAdminOut(**await _country_out(db, c))


@router.get("/{code}/versions", response_model=list[SettingsVersionOut])
async def country_versions(code: str, db: DB, admin: AdminUser) -> list[SettingsVersionOut]:
    return [
        SettingsVersionOut(**v)
        for v in await settings_versions.list_versions(db, "countries", code.upper(), with_data=True)
    ]


@router.put("/{code}", response_model=SettingsVersionOut)
async def update_country(
    code: str, body: VersionedUpdateIn, db: DB, admin: AdminUser, client: Client
) -> SettingsVersionOut:
    """Edit the current draft of this country, or create a new draft from the published version."""
    versions = await settings_versions.list_versions(db, "countries", code.upper())
    draft = next((v for v in versions if v["status"] == "draft"), None)
    if draft is not None:
        return SettingsVersionOut(
            **await settings_versions.update_version(
                db,
                "countries",
                draft["id"],
                {"name": body.name, "data": body.data, "change_note": body.change_note},
                admin.id,
                client.ip,
            )
        )
    if not versions:
        raise ApiError(ErrorCode.not_found, "Country not found; create it with POST")
    return SettingsVersionOut(
        **await settings_versions.create_draft(
            db,
            "countries",
            {"code": code.upper(), "name": body.name, "data": body.data, "change_note": body.change_note},
            admin.id,
            client.ip,
        )
    )
