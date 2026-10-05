"""GET /categories and GET /categories/{code}: published templates (questions + trait dimensions)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import DB
from app.errors import ApiError, ErrorCode
from app.models import CategoryTemplate
from app.schemas.config import CategorySummaryOut, CategoryTemplateOut, QuestionOut, TraitDimensionOut

router = APIRouter(prefix="/categories", tags=["config"])


def template_out(row: CategoryTemplate) -> dict[str, Any]:
    d = row.as_dict()
    d["questions"] = [
        QuestionOut(**{k: v for k, v in q.items() if k in QuestionOut.model_fields})
        for q in d.get("questions", [])
    ]
    d["trait_dimensions"] = [
        TraitDimensionOut(**{k: v for k, v in t.items() if k in TraitDimensionOut.model_fields})
        for t in d.get("trait_dimensions", [])
    ]
    return d


@router.get("", response_model=list[CategorySummaryOut])
async def list_categories(db: DB) -> list[CategorySummaryOut]:
    rows = (
        (
            await db.execute(
                select(CategoryTemplate)
                .where(CategoryTemplate.status == "published", CategoryTemplate.active.is_(True))
                .order_by(CategoryTemplate.code, CategoryTemplate.version.desc())
            )
        )
        .scalars()
        .all()
    )
    seen: set[str] = set()
    out = []
    for r in rows:
        if r.code in seen:
            continue
        seen.add(r.code)
        out.append(
            CategorySummaryOut(
                code=r.code,
                name=r.name,
                parent_code=r.parent_code,
                tags=list(r.tags or []),
                version=r.version,
                typical_goals=list(r.typical_goals or []),
            )
        )
    return out


@router.get("/{code}", response_model=CategoryTemplateOut)
async def get_category(code: str, db: DB) -> CategoryTemplateOut:
    row = (
        (
            await db.execute(
                select(CategoryTemplate)
                .where(CategoryTemplate.code == code, CategoryTemplate.status == "published")
                .order_by(CategoryTemplate.version.desc())
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise ApiError(ErrorCode.category_not_found, f"Category {code} not found")
    return CategoryTemplateOut(**template_out(row))
