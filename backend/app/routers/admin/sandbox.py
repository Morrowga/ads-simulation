"""POST /admin/sandbox/run."""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DB, AdminUser, Client
from app.schemas.admin import SandboxResultOut, SandboxRunIn
from app.services import audit, sandbox

router = APIRouter(prefix="/sandbox", tags=["admin"])


@router.post("/run", response_model=SandboxResultOut)
async def run_sandbox(body: SandboxRunIn, db: DB, admin: AdminUser, client: Client) -> SandboxResultOut:
    result = await sandbox.run_sandbox(db, body.model_dump())
    await audit.log(
        db,
        actor_id=admin.id,
        action="admin.sandbox.run",
        entity="sandbox",
        entity_id=body.sample,
        data={
            "use_drafts": body.use_drafts,
            "use_real_llm": body.use_real_llm,
            "runs": body.runs,
            "agents": body.agents,
            "elapsed_ms": result["elapsed_ms"],
        },
        ip=client.ip,
    )
    return SandboxResultOut(**result)
