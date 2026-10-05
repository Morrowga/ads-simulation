"""POST /admin/categories/draft-ai: the smart model drafts a full category template; saved as a draft version."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import tasks as llm_tasks
from app.llm.client import LLMClient
from app.services import settings_versions


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:64] or "category"


async def draft_with_ai(
    db: AsyncSession,
    *,
    name: str,
    code: str | None,
    parent_code: str | None,
    hints: str,
    actor_id: uuid.UUID | None,
    ip: str | None,
) -> dict[str, Any]:
    client = LLMClient(test_id=None)
    template = await llm_tasks.draft_category(
        client, name=name, code=code or slug(name), parent_code=parent_code, hints=hints
    )
    template["code"] = code or slug(template.get("code") or name)
    settings_versions.validate_category_data(template)
    payload = {
        "code": template["code"],
        "name": template["name"],
        "data": template,
        "change_note": f"AI draft from name '{name}' ({client.provider.name})",
    }
    out = await settings_versions.create_draft(db, "categories", payload, actor_id, ip)
    out["llm"] = {
        "provider": client.provider.name,
        "calls": client.totals.calls,
        "cost_usd": client.totals.cost_usd,
    }
    return out
