"""FastAPI application factory: routers, middleware, exception handlers, lifespan."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.db import dispose_engine
from app.errors import ApiError, ErrorCode
from app.logging_setup import configure_logging, request_id_var
from app.routers import (
    assets,
    auth,
    categories,
    checkout,
    confirm,
    countries,
    health,
    local_files,
    me,
    payments,
    platforms,
    profiles,
    progress,
    reports,
    stripe_webhook,
    tests,
)
from app.routers.admin import router as admin_router
from app.services import queue
from app.services.redis_client import close_redis
from app.services.storage import S3Storage, get_storage

log = logging.getLogger("advar.api")

TAGS = [
    {"name": "auth", "description": "Registration, e-mail verification, login, refresh, password reset"},
    {"name": "me", "description": "Current account"},
    {
        "name": "config",
        "description": "Public configuration for the wizard: countries, tiers, platforms, categories",
    },
    {"name": "profiles", "description": "Business profile presets with immutable versions"},
    {
        "name": "tests",
        "description": "Ad tests: drafts, assets, platforms, post settings, confirm, cancel, restart",
    },
    {"name": "progress", "description": "Live progress: stream token, SSE stream, snapshot"},
    {"name": "reports", "description": "Reports, PDF, comparison"},
    {"name": "checkout", "description": "Checkout, trial, card and manual payments"},
    {"name": "payments", "description": "Payment history and Stripe webhook"},
    {"name": "admin", "description": "Admin dashboard (role=admin, every action audit-logged)"},
    {"name": "health", "description": "Service health"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    configure_logging()
    s = get_settings()
    log.info(
        "api starting env=%s llm=%s payments=%s queue=%s storage=%s",
        s.APP_ENV,
        s.LLM_PROVIDER,
        s.PAYMENT_MODE,
        s.QUEUE_BACKEND,
        s.STORAGE_BACKEND,
    )
    st = get_storage()
    if isinstance(st, S3Storage):
        try:
            await st.ensure_bucket()
        except Exception as exc:  # noqa: BLE001
            log.warning("storage bucket check failed: %s", exc.__class__.__name__)
    yield
    await queue.close_pool()
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.APP_NAME} API",
        version="1.4.0",
        description="Virtual ad testing platform backend. All list endpoints use cursor pagination; every error uses {error: {code, message, details}}.",
        openapi_tags=TAGS,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # noqa: ANN001, ANN202
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details: list[dict[str, Any]] = []
        for e in exc.errors():
            details.append(
                {"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg"), "type": e.get("type")}
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.validation_error.value,
                    "message": "Request validation failed",
                    "details": details,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: ErrorCode.unauthorized,
            403: ErrorCode.forbidden,
            404: ErrorCode.not_found,
            405: ErrorCode.validation_error,
            409: ErrorCode.conflict,
            413: ErrorCode.asset_too_large,
            429: ErrorCode.rate_limited,
        }.get(exc.status_code, ErrorCode.internal_error)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code.value, "message": str(exc.detail), "details": None}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": ErrorCode.internal_error.value,
                    "message": "Internal server error",
                    "details": {"request_id": request_id_var.get()},
                }
            },
        )

    prefix = s.API_PREFIX
    app.include_router(local_files.router)
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(me.router, prefix=prefix)
    app.include_router(countries.router, prefix=prefix)
    app.include_router(platforms.router, prefix=prefix)
    app.include_router(categories.router, prefix=prefix)
    app.include_router(profiles.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)  # /tests/compare must be registered before /tests/{id}
    app.include_router(tests.router, prefix=prefix)
    app.include_router(assets.router, prefix=prefix)
    app.include_router(confirm.router, prefix=prefix)
    app.include_router(progress.router, prefix=prefix)
    app.include_router(checkout.router, prefix=prefix)
    app.include_router(payments.router, prefix=prefix)
    app.include_router(stripe_webhook.router, prefix=prefix)
    app.include_router(admin_router, prefix=prefix)
    return app


app = create_app()
