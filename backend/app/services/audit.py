"""Audit log writer for admin and payment actions."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | uuid.UUID | None,
    data: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        data=_jsonable(data or {}),
        ip=ip,
    )
    db.add(row)
    await db.flush()
    return row


async def entries_for(
    db: AsyncSession, entity: str, entity_id: str | uuid.UUID, limit: int = 50
) -> list[AuditLog]:
    res = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity == entity, AuditLog.entity_id == str(entity_id))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)
