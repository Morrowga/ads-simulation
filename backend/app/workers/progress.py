"""Progress events: publish to Redis channel progress:{test_id} and keep the latest snapshot
at progress:last:{test_id} (TTL 24 h). Comment events are throttled to 2 per second."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.services.redis_client import get_redis

SNAPSHOT_TTL = 24 * 3600
STAGE_LABELS = {
    "prepare": "Preparing the test",
    "analyze_ad": "Reading the ad",
    "population": "Building the virtual audience",
    "archetypes": "Grouping customer types",
    "react": "Customers reacting",
    "simulate": "Running the virtual campaign",
    "explain": "Writing reasons from evidence",
    "export": "Saving the report",
}


def channel(test_id: uuid.UUID | str) -> str:
    return f"progress:{test_id}"


def snapshot_key(test_id: uuid.UUID | str) -> str:
    return f"progress:last:{test_id}"


class Publisher:
    def __init__(self, test_id: uuid.UUID | str) -> None:
        self.test_id = str(test_id)
        self.redis = get_redis()
        self.snapshot: dict[str, Any] = {
            "test_id": self.test_id,
            "status": "running",
            "stage": None,
            "pct": 0,
            "cancel_window": True,
            "runs_done": 0,
            "runs_target": 0,
        }
        self._last_comment = 0.0
        self._comment_interval = 0.5

    async def _emit(self, event: str, data: dict[str, Any]) -> None:
        payload = json.dumps({"event": event, "data": data, "ts": datetime.now(UTC).isoformat()}, default=str)
        await self.redis.publish(channel(self.test_id), payload)
        self.snapshot["last_event"] = event
        self.snapshot["updated_at"] = datetime.now(UTC).isoformat()
        await self.redis.set(
            snapshot_key(self.test_id), json.dumps(self.snapshot, default=str), ex=SNAPSHOT_TTL
        )

    async def stage(
        self,
        stage: str,
        pct: int,
        cancel_window: bool,
        label: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.snapshot.update(
            {
                "status": "running",
                "stage": stage,
                "pct": int(pct),
                "label": label or STAGE_LABELS.get(stage, stage),
                "cancel_window": cancel_window,
            }
        )
        data = {
            "stage": stage,
            "pct": int(pct),
            "label": self.snapshot["label"],
            "cancel_window": cancel_window,
        }
        if extra:
            data.update(extra)
        await self._emit("stage", data)

    async def run_batch(
        self,
        *,
        pct: int,
        runs_done: int,
        runs_target: int,
        batch: list[dict[str, Any]],
        estimate: dict[str, Any],
        funnel: dict[str, Any],
        confidence: str,
        platform: str,
        audience_idx: int,
    ) -> None:
        self.snapshot.update(
            {
                "stage": "simulate",
                "pct": int(pct),
                "cancel_window": False,
                "runs_done": runs_done,
                "runs_target": runs_target,
                "estimate": estimate,
                "funnel": funnel,
                "confidence": confidence,
            }
        )
        await self._emit(
            "run_batch",
            {
                "stage": "simulate",
                "pct": int(pct),
                "runs_done": runs_done,
                "runs_target": runs_target,
                "platform": platform,
                "audience_idx": audience_idx,
                "batch": [
                    {
                        "run": b.get("run_no"),
                        "scenario": b.get("scenario"),
                        "score": b.get("score"),
                        "ctr": b["rates"].get("ctr"),
                        "buys": b["counts"].get("bought"),
                        "goal_value": b.get("goal_value"),
                    }
                    for b in batch
                ],
                "estimate": estimate,
                "funnel": funnel,
                "confidence": confidence,
                "cancel_window": False,
            },
        )

    async def comment(
        self, archetype: str, text: str, topic: str | None, platform: str, language_group: str
    ) -> None:
        now = time.monotonic()
        if now - self._last_comment < self._comment_interval:
            return
        self._last_comment = now
        await self._emit(
            "comment",
            {
                "archetype": archetype,
                "text": text,
                "topic": topic,
                "platform": platform,
                "language_group": language_group,
            },
        )

    async def completed(self, score: float | None, report_url: str) -> None:
        self.snapshot.update(
            {"status": "completed", "stage": "export", "pct": 100, "cancel_window": False, "score": score}
        )
        await self._emit("completed", {"score": score, "report_url": report_url, "pct": 100})

    async def failed(self, code: str, message: str, rerun_available: bool) -> None:
        self.snapshot.update(
            {"status": "failed", "cancel_window": False, "error": {"code": code, "message": message}}
        )
        await self._emit("failed", {"code": code, "message": message, "rerun_available": rerun_available})

    async def cancelled(self, free_restart: bool) -> None:
        self.snapshot.update({"status": "draft", "cancel_window": False})
        await self._emit("cancelled", {"free_restart": free_restart})


async def read_snapshot(test_id: uuid.UUID | str) -> dict[str, Any] | None:
    raw = await get_redis().get(snapshot_key(test_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
