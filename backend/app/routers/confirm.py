"""POST /tests/{id}/confirm."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app.schemas.tests import ConfirmOut
from app.services import confirm as confirm_service

router = APIRouter(prefix="/tests", tags=["tests"])


@router.post("/{test_id}/confirm", response_model=ConfirmOut)
async def confirm_test(test_id: uuid.UUID, db: DB, user: CurrentUser) -> ConfirmOut:
    return ConfirmOut(**await confirm_service.run_confirm(db, user, test_id))
