import { describe, expect, it } from "vitest";
import { AppError, ERROR_MESSAGE_KEYS, toAppError } from "@/lib/errors";

describe("toAppError", () => {
  it("maps the backend error envelope", () => {
    const e = toAppError(422, {
      error: { code: "profile_invalid", message: "bad", details: { fields: { followers: "required" } } },
    });
    expect(e).toBeInstanceOf(AppError);
    expect(e.code).toBe("profile_invalid");
    expect(e.status).toBe(422);
    expect(e.fieldErrors).toEqual({ followers: "required" });
  });
  it("exposes confirm blocking errors", () => {
    const e = toAppError(422, {
      error: { code: "validation_error", message: "x", details: { errors: ["No media", "No platform"] } },
    });
    expect(e.errorList).toEqual(["No media", "No platform"]);
  });
  it("falls back for non-JSON bodies", () => {
    expect(toAppError(502, null).code).toBe("unknown");
    expect(toAppError(0, null).code).toBe("network_error");
  });
  it("has a translation key for every known code", () => {
    for (const code of [
      "duplicate_test",
      "cancel_window_closed",
      "payment_required",
      "trial_not_available",
    ]) {
      expect(ERROR_MESSAGE_KEYS[code]).toBe(`errors.${code}`);
    }
  });
});
