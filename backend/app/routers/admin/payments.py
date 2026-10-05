"""Admin payments: manual order queue (search by payment code), approve, cancel, refund."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import DB, AdminUser, Client, Page
from app.models import Payment
from app.schemas.common import Page as PageOut
from app.schemas.payments import AdminPaymentOut, ApproveIn, CancelIn, RefundIn
from app.services import payments as payment_service
from app.services import serializers
from app.services.payments import manual
from app.services.tests_service import decode_cursor, encode_cursor

router = APIRouter(prefix="/payments", tags=["admin"])


@router.get("", response_model=PageOut[AdminPaymentOut])
async def list_payments(
    db: DB,
    admin: AdminUser,
    page: Page,
    status: str | None = Query(default=None),
    code: str | None = Query(default=None, description="Payment code search"),
    method: str | None = Query(default=None),
    sort: str | None = Query(
        default=None, description="newest | oldest (pending_review defaults to oldest first)"
    ),
) -> PageOut[AdminPaymentOut]:
    oldest = sort == "oldest" or (sort is None and status == "pending_review")
    order = (
        (Payment.created_at.asc(), Payment.id.asc())
        if oldest
        else (Payment.created_at.desc(), Payment.id.desc())
    )
    stmt = select(Payment).order_by(*order).limit(page.limit + 1)
    if status:
        stmt = stmt.where(Payment.status == status)
    if method:
        stmt = stmt.where(Payment.method == method)
    if code:
        stmt = stmt.where(Payment.payment_code.ilike(f"%{code.strip().upper()}%"))
    cur = decode_cursor(page.cursor)
    if cur:
        t, rid = cur
        if oldest:
            stmt = stmt.where((Payment.created_at > t) | ((Payment.created_at == t) & (Payment.id > rid)))
        else:
            stmt = stmt.where((Payment.created_at < t) | ((Payment.created_at == t) & (Payment.id < rid)))
    rows = list((await db.execute(stmt)).scalars().all())
    next_cursor = None
    if len(rows) > page.limit:
        rows = rows[: page.limit]
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)
    return PageOut[AdminPaymentOut](
        items=[AdminPaymentOut(**await serializers.admin_payment_out(db, p)) for p in rows],
        next_cursor=next_cursor,
    )


@router.post("/{payment_id}/approve", response_model=AdminPaymentOut)
async def approve_payment(
    payment_id: uuid.UUID, db: DB, admin: AdminUser, client: Client, body: ApproveIn | None = None
) -> AdminPaymentOut:
    p = await manual.approve(db, admin, payment_id, body.admin_reference if body else None, client.ip)
    return AdminPaymentOut(**await serializers.admin_payment_out(db, p))


@router.post("/{payment_id}/cancel", response_model=AdminPaymentOut)
async def cancel_payment(
    payment_id: uuid.UUID, body: CancelIn, db: DB, admin: AdminUser, client: Client
) -> AdminPaymentOut:
    p = await manual.cancel(db, admin, payment_id, body.reason, client.ip)
    return AdminPaymentOut(**await serializers.admin_payment_out(db, p))


@router.post("/{payment_id}/refund", response_model=AdminPaymentOut)
async def refund_payment(
    payment_id: uuid.UUID, db: DB, admin: AdminUser, client: Client, body: RefundIn | None = None
) -> AdminPaymentOut:
    p = await payment_service.refund(
        db,
        admin,
        payment_id,
        body.reason if body else "",
        body.manual_refund_reference if body else None,
        client.ip,
    )
    return AdminPaymentOut(**await serializers.admin_payment_out(db, p))
