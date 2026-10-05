"""Reports: JSON, PDF (presigned URL) and side-by-side comparison."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.deps import DB, CurrentUser
from app.schemas.tests import CompareOut, ReportOut, ReportPdfOut
from app.services import reports as report_service

router = APIRouter(prefix="/tests", tags=["reports"])


@router.get("/compare", response_model=CompareOut)
async def compare_tests(
    db: DB, user: CurrentUser, a: uuid.UUID = Query(...), b: uuid.UUID = Query(...)
) -> CompareOut:
    return CompareOut(**await report_service.compare(db, user, a, b))


@router.get("/{test_id}/report", response_model=ReportOut)
async def get_report(test_id: uuid.UUID, db: DB, user: CurrentUser) -> ReportOut:
    return ReportOut(**await report_service.get_report(db, user, test_id))


@router.get("/{test_id}/report.pdf", response_model=ReportPdfOut)
async def get_report_pdf(test_id: uuid.UUID, db: DB, user: CurrentUser) -> ReportPdfOut:
    url, ttl = await report_service.pdf_url(db, user, test_id)
    return ReportPdfOut(url=url, expires_in=ttl)
