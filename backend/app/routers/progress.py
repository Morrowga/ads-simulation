"""Live progress: stream token, SSE stream (authenticated by the short-lived token), snapshot."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.db import get_session_factory
from app.deps import DB, CurrentUser
from app.errors import ApiError, ErrorCode
from app.models import AdTest
from app.schemas.auth import StreamTokenOut
from app.schemas.tests import ProgressSnapshot
from app.security import create_stream_token, decode_stream_token
from app.services import serializers, tests_service
from app.services.redis_client import get_redis
from app.workers.progress import STAGE_LABELS, channel, read_snapshot

router = APIRouter(prefix="/tests", tags=["progress"])
HEARTBEAT_SEC = 15


@router.post("/{test_id}/progress/token", response_model=StreamTokenOut)
async def progress_token(test_id: uuid.UUID, db: DB, user: CurrentUser) -> StreamTokenOut:
    await tests_service.get_owned(db, user, test_id)
    s = get_settings()
    token = create_stream_token(user.id, test_id)
    return StreamTokenOut(
        stream_token=token,
        expires_in=s.STREAM_TOKEN_TTL_SEC,
        url=f"{s.API_PREFIX}/tests/{test_id}/progress?st={token}",
    )


async def _snapshot_dict(test: AdTest) -> dict[str, Any]:
    snap = await read_snapshot(test.id) or {}
    return {
        "test_id": test.id,
        "status": test.status,
        "stage": snap.get("stage") or test.stage,
        "pct": int(snap.get("pct", test.progress_pct))
        if test.status == "running"
        else (100 if test.status == "completed" else test.progress_pct),
        "label": snap.get("label") or STAGE_LABELS.get(test.stage or "", None),
        "cancel_window": serializers.cancel_window(test),
        "runs_done": int(snap.get("runs_done", 0)),
        "runs_target": int(snap.get("runs_target", 0)),
        "estimate": snap.get("estimate"),
        "funnel": snap.get("funnel"),
        "confidence": snap.get("confidence"),
        "last_event": snap.get("last_event"),
        "updated_at": snap.get("updated_at"),
        "error": test.error,
    }


@router.get("/{test_id}/progress/snapshot", response_model=ProgressSnapshot)
async def progress_snapshot(test_id: uuid.UUID, db: DB, user: CurrentUser) -> ProgressSnapshot:
    test = await tests_service.get_owned(db, user, test_id)
    return ProgressSnapshot(**await _snapshot_dict(test))


@router.get(
    "/{test_id}/progress",
    response_class=EventSourceResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of stage, run_batch, comment, completed, failed and cancelled events",
        }
    },
)
async def progress_stream(
    test_id: uuid.UUID,
    request: Request,
    st: str = Query(..., description="Stream token from POST /tests/{id}/progress/token"),
) -> EventSourceResponse:
    user_id, token_test_id = decode_stream_token(st)
    if token_test_id != test_id:
        raise ApiError(ErrorCode.forbidden, "Stream token is for another test")
    async with get_session_factory()() as db:
        test = await db.get(AdTest, test_id)
        if test is None or test.user_id != user_id:
            raise ApiError(ErrorCode.not_found, "Test not found")
        initial = await _snapshot_dict(test)
        initial_status = test.status

    async def gen() -> AsyncIterator[dict[str, Any]]:
        # 1) subscribe FIRST so no event can fall between the snapshot read and the subscription
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel(test_id))
        try:
            # 2) now read the current state (fresh, after subscribing)
            async with get_session_factory()() as db2:
                fresh = await db2.get(AdTest, test_id)
                if fresh is None:
                    return
                current = await _snapshot_dict(fresh)
                current_status = fresh.status

            yield {"event": "snapshot", "data": json.dumps(current, default=str)}
            if current_status in ("completed", "failed", "refunded"):
                final_event = "completed" if current_status == "completed" else "failed"
                payload = (
                    {
                        "score": current.get("estimate", {}).get("score") if current.get("estimate") else None,
                        "report_url": f"/tests/{test_id}/report",
                    }
                    if final_event == "completed"
                    else {
                        "code": (current.get("error") or {}).get("code", "failed"),
                        "message": (current.get("error") or {}).get("message", ""),
                        "rerun_available": True,
                    }
                )
                yield {"event": final_event, "data": json.dumps(payload, default=str)}
                return

            last_beat = asyncio.get_running_loop().time()
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                now = asyncio.get_running_loop().time()
                if msg is not None and msg.get("type") == "message":
                    try:
                        body = json.loads(msg["data"])
                    except (TypeError, json.JSONDecodeError):
                        continue
                    yield {
                        "event": body.get("event", "message"),
                        "data": json.dumps(body.get("data", {}), default=str),
                    }
                    if body.get("event") in ("completed", "failed", "cancelled"):
                        break
                    last_beat = now
                elif now - last_beat >= HEARTBEAT_SEC:
                    yield {"comment": "heartbeat"}
                    last_beat = now
        finally:
            await pubsub.unsubscribe(channel(test_id))
            await pubsub.aclose()

    return EventSourceResponse(gen(), ping=HEARTBEAT_SEC)
