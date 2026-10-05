"""GET /payments: my payment history."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB, CurrentUser, Page
from app.models import Payment
from app.schemas.common import Page as PageOut
from app.schemas.payments import PaymentOut
from app.services import serializers
from app.services.tests_service import decode_cursor, encode_cursor

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=PageOut[PaymentOut])
async def list_payments(db: DB, user: CurrentUser, page: Page) -> PageOut[PaymentOut]:
    stmt = (
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .limit(page.limit + 1)
    )
    cur = decode_cursor(page.cursor)
    if cur:
        t, rid = cur
        stmt = stmt.where((Payment.created_at < t) | ((Payment.created_at == t) & (Payment.id < rid)))
    rows = list((await db.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > page.limit:
        rows = rows[: page.limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)
    return PageOut[PaymentOut](
        items=[PaymentOut(**serializers.payment_out(p)) for p in rows], next_cursor=next_cursor
    )
