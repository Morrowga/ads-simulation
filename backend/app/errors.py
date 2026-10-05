"""API error type and the stable error-code enum used in every error response."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    # generic
    validation_error = "validation_error"
    not_found = "not_found"
    forbidden = "forbidden"
    unauthorized = "unauthorized"
    conflict = "conflict"
    rate_limited = "rate_limited"
    internal_error = "internal_error"
    # auth
    invalid_credentials = "invalid_credentials"
    email_taken = "email_taken"
    email_not_verified = "email_not_verified"
    invalid_token = "invalid_token"
    token_expired = "token_expired"
    account_blocked = "account_blocked"
    # tests / state
    invalid_state = "invalid_state"
    test_not_editable = "test_not_editable"
    cancel_window_closed = "cancel_window_closed"
    restart_not_available = "restart_not_available"
    duplicate_test = "duplicate_test"
    confirm_required = "confirm_required"
    budget_required = "budget_required"
    budget_not_allowed = "budget_not_allowed"
    budget_shares_invalid = "budget_shares_invalid"
    goal_not_supported = "goal_not_supported"
    platform_not_available = "platform_not_available"
    schedule_invalid = "schedule_invalid"
    asset_invalid = "asset_invalid"
    asset_too_large = "asset_too_large"
    profile_invalid = "profile_invalid"
    audience_invalid = "audience_invalid"
    # payments
    payment_required = "payment_required"
    method_not_allowed = "method_not_allowed"
    trial_not_available = "trial_not_available"
    trial_review_required = "trial_review_required"
    payment_invalid_state = "payment_invalid_state"
    payment_not_found = "payment_not_found"
    stripe_signature_invalid = "stripe_signature_invalid"
    stripe_not_configured = "stripe_not_configured"
    # llm / worker
    llm_not_configured = "llm_not_configured"
    llm_budget_exceeded = "llm_budget_exceeded"
    llm_daily_cap_reached = "llm_daily_cap_reached"
    llm_unavailable = "llm_unavailable"
    engine_error = "engine_error"
    # settings
    settings_version_invalid = "settings_version_invalid"
    settings_not_draft = "settings_not_draft"
    settings_not_published = "settings_not_published"
    country_not_active = "country_not_active"
    category_not_found = "category_not_found"


STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.validation_error: 422,
    ErrorCode.not_found: 404,
    ErrorCode.forbidden: 403,
    ErrorCode.unauthorized: 401,
    ErrorCode.conflict: 409,
    ErrorCode.rate_limited: 429,
    ErrorCode.internal_error: 500,
    ErrorCode.invalid_credentials: 401,
    ErrorCode.email_taken: 409,
    ErrorCode.email_not_verified: 403,
    ErrorCode.invalid_token: 400,
    ErrorCode.token_expired: 400,
    ErrorCode.account_blocked: 403,
    ErrorCode.invalid_state: 409,
    ErrorCode.test_not_editable: 409,
    ErrorCode.cancel_window_closed: 409,
    ErrorCode.restart_not_available: 409,
    ErrorCode.duplicate_test: 409,
    ErrorCode.confirm_required: 409,
    ErrorCode.budget_required: 422,
    ErrorCode.budget_not_allowed: 422,
    ErrorCode.budget_shares_invalid: 422,
    ErrorCode.goal_not_supported: 422,
    ErrorCode.platform_not_available: 422,
    ErrorCode.schedule_invalid: 422,
    ErrorCode.asset_invalid: 422,
    ErrorCode.asset_too_large: 413,
    ErrorCode.profile_invalid: 422,
    ErrorCode.audience_invalid: 422,
    ErrorCode.payment_required: 402,
    ErrorCode.method_not_allowed: 403,
    ErrorCode.trial_not_available: 409,
    ErrorCode.trial_review_required: 409,
    ErrorCode.payment_invalid_state: 409,
    ErrorCode.payment_not_found: 404,
    ErrorCode.stripe_signature_invalid: 400,
    ErrorCode.stripe_not_configured: 503,
    ErrorCode.llm_not_configured: 503,
    ErrorCode.llm_budget_exceeded: 503,
    ErrorCode.llm_daily_cap_reached: 503,
    ErrorCode.llm_unavailable: 503,
    ErrorCode.engine_error: 500,
    ErrorCode.settings_version_invalid: 422,
    ErrorCode.settings_not_draft: 409,
    ErrorCode.settings_not_published: 409,
    ErrorCode.country_not_active: 422,
    ErrorCode.category_not_found: 404,
}


class ApiError(Exception):
    """Raised anywhere in services/routers; rendered as {"error": {code, message, details}}."""

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        self.code = ErrorCode(code)
        self.message = message or self.code.replace("_", " ")
        self.details = details
        self.status_code = status_code or STATUS_BY_CODE.get(self.code, 400)
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code.value, "message": self.message, "details": self.details}}
