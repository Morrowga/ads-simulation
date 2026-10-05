"""Admin router (role=admin)."""

from fastapi import APIRouter

from app.routers.admin import (
    categories,
    countries,
    fx_rates,
    metrics,
    payments,
    platforms,
    prices,
    sandbox,
    scenarios,
    settings,
    tests,
    users,
    weights,
)

router = APIRouter(prefix="/admin")
for sub in (
    payments,
    tests,
    users,
    prices,
    settings,
    countries,
    categories,
    platforms,
    scenarios,
    weights,
    fx_rates,
    sandbox,
    metrics,
):
    router.include_router(sub.router)

__all__ = ["router"]
