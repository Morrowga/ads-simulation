"""Structured JSON logging with request id and test id, no secrets."""

from __future__ import annotations

import contextvars
import logging
import sys

from pythonjsonlogger import json as jsonlogger

from app.config import get_settings

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
test_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("test_id", default=None)

SECRET_KEYS = ("password", "authorization", "api_key", "secret", "token", "cookie")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.test_id = test_id_var.get()
        msg = str(record.getMessage())
        low = msg.lower()
        if any(k in low for k in SECRET_KEYS) and "=" in msg:
            record.msg = "[redacted: message contained a secret-like key]"
            record.args = ()
        return True


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(test_id)s")
    )
    handler.addFilter(ContextFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, s.LOG_LEVEL.upper(), logging.INFO))
    for noisy in ("uvicorn.access", "botocore", "boto3", "httpx", "httpcore", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True
