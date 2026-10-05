"""GET/PATCH/DELETE /me."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app.schemas.auth import MeOut, MeUpdateIn
from app.schemas.common import OkOut
from app.services import auth_service, serializers

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeOut)
async def get_me(db: DB, user: CurrentUser) -> MeOut:
    return MeOut(**await serializers.me_out(db, user))


@router.patch("", response_model=MeOut)
async def patch_me(body: MeUpdateIn, db: DB, user: CurrentUser) -> MeOut:
    await auth_service.update_me(db, user, name=body.name, locale=body.locale, country=body.country)
    return MeOut(**await serializers.me_out(db, user))


@router.delete("", response_model=OkOut)
async def delete_me(db: DB, user: CurrentUser) -> OkOut:
    await auth_service.delete_me(db, user)
    return OkOut(message="Account deleted and anonymised")
