"""Typed application settings loaded from environment variables (pydantic-settings)."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["local", "test", "production"]
PaymentMode = Literal["mock", "stripe_test", "stripe_live"]
LLMProvider = Literal["openai", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    # --- app ---
    APP_ENV: AppEnv = "local"
    APP_NAME: str = "ADVAR"
    BASE_CURRENCY: str = "USD"
    API_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000"
    ENGINE_VERSION: str = "3.2.0"
    LOG_LEVEL: str = "INFO"
    API_BASE_URL: str = "http://localhost:8000"

    # --- database / redis ---
    DATABASE_URL: str = "postgresql+asyncpg://advar:advar@postgres:5432/advar"
    REDIS_URL: str = "redis://redis:6379/0"

    # --- auth ---
    JWT_SECRET: str = "change-me"
    JWT_ACCESS_TTL_MIN: int = 15
    JWT_REFRESH_TTL_DAYS: int = 30
    STREAM_TOKEN_TTL_SEC: int = 60
    COOKIE_DOMAIN: str = "localhost"
    COOKIE_SECURE: bool = False

    # --- storage ---
    STORAGE_BACKEND: Literal["s3", "memory", "local"] = "s3"
    STORAGE_LOCAL_DIR: str = "/tmp/advar-storage"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "advar"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_REGION: str = "us-east-1"
    PRESIGNED_URL_TTL_SEC: int = 600

    # --- email ---
    MAIL_BACKEND: Literal["smtp", "memory"] = "smtp"
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_TLS: bool = False
    MAIL_FROM: str = "ADVAR <no-reply@advar.local>"

    # --- LLM ---
    LLM_PROVIDER: LLMProvider = "mock"
    OPENAI_API_KEY: str = ""
    LLM_MODEL_AGENT: str = "gpt-5.6-luna"
    LLM_MODEL_SMART: str = "gpt-5.6-terra"
    LLM_MODEL_TRANSCRIBE: str = "gpt-transcribe"
    LLM_MAX_CONCURRENCY: int = 64
    LLM_TEST_TOKEN_BUDGET: int = 3_000_000
    DAILY_LLM_SPEND_CAP_USD: float = 50.0
    LLM_PRICE_JSON: str = (
        '{"gpt-5.6-luna":{"in":0.20,"cached_in":0.02,"out":1.20},'
        '"gpt-5.6-terra":{"in":2.00,"cached_in":0.20,"out":12.00}}'
    )

    # --- payments ---
    PAYMENT_MODE: PaymentMode = "mock"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    MANUAL_ORDER_EXPIRY_HOURS: int = 48
    MANUAL_AUTO_APPROVE_IN_MOCK: bool = False

    # --- queue / worker ---
    QUEUE_BACKEND: Literal["arq", "inline"] = "arq"
    JOB_TIMEOUT_SEC: int = 1200
    STUCK_RUNNING_MINUTES: int = 30
    DRAFT_EXPIRY_DAYS: int = 30

    # --- seed ---
    SEED_ADMIN_EMAIL: str = "admin@advar.local"
    SEED_ADMIN_PASSWORD: str = "admin12345"

    # --- limits ---
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024
    MAX_VIDEO_BYTES: int = 50 * 1024 * 1024
    MAX_VIDEO_SECONDS: float = 60.0

    @field_validator("API_PREFIX")
    @classmethod
    def _prefix(cls, v: str) -> str:
        v = "/" + v.strip("/")
        return "" if v == "/" else v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def llm_prices(self) -> dict[str, dict[str, float]]:
        try:
            data = json.loads(self.LLM_PRICE_JSON or "{}")
        except json.JSONDecodeError:
            return {}
        return {k: {kk: float(vv) for kk, vv in v.items()} for k, v in data.items()}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.APP_ENV == "production":
            problems = []
            if self.PAYMENT_MODE == "mock":
                problems.append("PAYMENT_MODE=mock is not allowed in production")
            if self.LLM_PROVIDER == "mock":
                problems.append("LLM_PROVIDER=mock is not allowed in production")
            if self.JWT_SECRET in ("", "change-me"):
                problems.append("JWT_SECRET must be set to a strong secret in production")
            if self.STORAGE_BACKEND != "s3" or self.MAIL_BACKEND != "smtp" or self.QUEUE_BACKEND != "arq":
                problems.append("memory/inline backends are not allowed in production")
            if problems:
                raise ValueError("; ".join(problems))
        if self.PAYMENT_MODE == "stripe_live" and self.APP_ENV != "production":
            raise ValueError("PAYMENT_MODE=stripe_live is only allowed when APP_ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Tests set environment variables before the first call."""
    return Settings()
