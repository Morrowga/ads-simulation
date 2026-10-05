"""Report access and comparison of two completed tests."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ApiError, ErrorCode
from app.models import Report, User
from app.services import serializers, storage, tests_service

COMPARE_METRICS = (
    "reach_rate",
    "stop_rate",
    "ctr",
    "buy_rate",
    "cvr",
    "message_rate",
    "engagement_rate",
    "comment_rate",
    "share_rate",
    "save_rate",
    "frequency",
)


async def get_report(db: AsyncSession, user: User, test_id: uuid.UUID) -> dict[str, Any]:
    test = await tests_service.get_owned(db, user, test_id)
    if test.status not in ("completed", "refunded"):
        raise ApiError(
            ErrorCode.invalid_state,
            f"Report is not ready (status: {test.status})",
            details={"status": test.status},
        )
    report = await db.get(Report, test.id)
    if report is None:
        raise ApiError(ErrorCode.not_found, "Report not found")
    return serializers.report_out(test, report)


async def pdf_url(db: AsyncSession, user: User, test_id: uuid.UUID) -> tuple[str, int]:
    test = await tests_service.get_owned(db, user, test_id)
    report = await db.get(Report, test.id)
    if report is None or not report.pdf_key:
        raise ApiError(ErrorCode.not_found, "PDF not available yet")
    ttl = get_settings().PRESIGNED_URL_TTL_SEC
    url = await storage.get_storage().presigned_url(
        report.pdf_key, ttl, filename=f"advar-report-{test.id}.pdf"
    )
    return url, ttl


def _p50(d: Any) -> float | None:
    if isinstance(d, dict):
        v = d.get("p50")
        return float(v) if v is not None else None
    if isinstance(d, (int, float)):
        return float(d)
    return None


async def compare(db: AsyncSession, user: User, a_id: uuid.UUID, b_id: uuid.UUID) -> dict[str, Any]:
    if a_id == b_id:
        raise ApiError(ErrorCode.validation_error, "Choose two different tests")
    a = await get_report(db, user, a_id)
    b = await get_report(db, user, b_id)
    metrics: list[dict[str, Any]] = []
    metrics.append(
        {
            "metric": "score",
            "a": a["score"],
            "b": b["score"],
            "delta": (b["score"] - a["score"]) if a["score"] is not None and b["score"] is not None else None,
        }
    )
    ga, gb = a["headline_metric"], b["headline_metric"]
    metrics.append(
        {
            "metric": f"goal:{ga.get('metric')}",
            "a": _p50(ga.get("value")),
            "b": _p50(gb.get("value")),
            "delta": _delta(_p50(ga.get("value")), _p50(gb.get("value"))),
            "note": None
            if ga.get("metric") == gb.get("metric")
            else f"different goals ({ga.get('metric')} vs {gb.get('metric')})",
        }
    )
    ra, rb = a["summary"].get("rates") or {}, b["summary"].get("rates") or {}
    for m in COMPARE_METRICS:
        va, vb = _p50(ra.get(m)), _p50(rb.get(m))
        metrics.append({"metric": m, "a": va, "b": vb, "delta": _delta(va, vb)})
    ca, cb = a["summary"].get("counts") or {}, b["summary"].get("counts") or {}
    for m in ("seen", "stopped", "clicked", "messaged", "bought", "engagements"):
        va, vb = _p50(ca.get(m)), _p50(cb.get(m))
        metrics.append({"metric": f"count:{m}", "a": va, "b": vb, "delta": _delta(va, vb)})
    differences = []
    if a["post_type"] != b["post_type"]:
        differences.append(f"post type: {a['post_type']} vs {b['post_type']}")
    if a["goal"] != b["goal"]:
        differences.append(f"goal: {a['goal']} vs {b['goal']}")
    pa = sorted(p.get("code") for p in a["platforms"])
    pb = sorted(p.get("code") for p in b["platforms"])
    if pa != pb:
        differences.append(f"platforms: {', '.join(pa)} vs {', '.join(pb)}")
    ba, bb = a["summary"].get("budget_usd"), b["summary"].get("budget_usd")
    if ba != bb:
        differences.append(f"budget: {ba} vs {bb} USD")
    if a["settings_versions"] != b["settings_versions"]:
        differences.append("settings versions differ")
    if a["engine_version"] != b["engine_version"]:
        differences.append(f"engine version: {a['engine_version']} vs {b['engine_version']}")
    return {"a": a, "b": b, "metrics": metrics, "differences": differences}


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(b - a, 6)
