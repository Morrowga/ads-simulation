/** Backend error shape {"error": {"code", "message", "details"}} mapped to one AppError type. */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export class AppError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /** `details.fields` from profile_invalid / validation errors: {field: message}. */
  get fieldErrors(): Record<string, string> {
    const d = this.details as { fields?: Record<string, string> } | null | undefined;
    return d && typeof d === "object" && d.fields && typeof d.fields === "object" ? d.fields : {};
  }

  /** `details.errors` from confirm: string[] blocking list. */
  get errorList(): string[] {
    const d = this.details as { errors?: unknown } | null | undefined;
    return d && typeof d === "object" && Array.isArray(d.errors) ? d.errors.map(String) : [];
  }
}

export function isAppError(e: unknown): e is AppError {
  return e instanceof AppError;
}

export function toAppError(status: number, body: unknown): AppError {
  const b = body as Partial<ApiErrorBody> | null;
  if (b && typeof b === "object" && b.error && typeof b.error === "object") {
    return new AppError(
      String(b.error.code ?? "unknown"),
      String(b.error.message ?? "Request failed"),
      status,
      b.error.details,
    );
  }
  return new AppError(
    status === 0 ? "network_error" : "unknown",
    status === 0 ? "Network error" : `Request failed (${status})`,
    status,
    body,
  );
}

/**
 * Translation keys for known backend error codes (messages/en.json -> errors.*).
 * Unknown codes fall back to the backend message.
 */
export const ERROR_MESSAGE_KEYS: Record<string, string> = {
  validation_error: "errors.validation_error",
  not_found: "errors.not_found",
  forbidden: "errors.forbidden",
  unauthorized: "errors.unauthorized",
  conflict: "errors.conflict",
  rate_limited: "errors.rate_limited",
  internal_error: "errors.internal_error",
  invalid_credentials: "errors.invalid_credentials",
  email_taken: "errors.email_taken",
  email_not_verified: "errors.email_not_verified",
  invalid_token: "errors.invalid_token",
  token_expired: "errors.token_expired",
  account_blocked: "errors.account_blocked",
  invalid_state: "errors.invalid_state",
  test_not_editable: "errors.test_not_editable",
  cancel_window_closed: "errors.cancel_window_closed",
  restart_not_available: "errors.restart_not_available",
  duplicate_test: "errors.duplicate_test",
  confirm_required: "errors.confirm_required",
  budget_required: "errors.budget_required",
  budget_not_allowed: "errors.budget_not_allowed",
  budget_shares_invalid: "errors.budget_shares_invalid",
  goal_not_supported: "errors.goal_not_supported",
  platform_not_available: "errors.platform_not_available",
  schedule_invalid: "errors.schedule_invalid",
  asset_invalid: "errors.asset_invalid",
  asset_too_large: "errors.asset_too_large",
  profile_invalid: "errors.profile_invalid",
  audience_invalid: "errors.audience_invalid",
  payment_required: "errors.payment_required",
  method_not_allowed: "errors.method_not_allowed",
  trial_not_available: "errors.trial_not_available",
  trial_review_required: "errors.trial_review_required",
  payment_invalid_state: "errors.payment_invalid_state",
  payment_not_found: "errors.payment_not_found",
  stripe_not_configured: "errors.stripe_not_configured",
  llm_not_configured: "errors.llm_not_configured",
  llm_budget_exceeded: "errors.llm_budget_exceeded",
  llm_daily_cap_reached: "errors.llm_daily_cap_reached",
  llm_unavailable: "errors.llm_unavailable",
  engine_error: "errors.engine_error",
  settings_version_invalid: "errors.settings_version_invalid",
  settings_not_draft: "errors.settings_not_draft",
  settings_not_published: "errors.settings_not_published",
  country_not_active: "errors.country_not_active",
  category_not_found: "errors.category_not_found",
  network_error: "errors.network_error",
  unknown: "errors.unknown",
};
