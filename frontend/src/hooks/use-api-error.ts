"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { ERROR_MESSAGE_KEYS, isAppError } from "@/lib/errors";

/** Maps an AppError (or anything thrown) to a translated, user-facing message. */
export function useApiError(): (error: unknown) => string {
  const t = useTranslations();
  return useCallback(
    (error: unknown) => {
      if (isAppError(error)) {
        const key = ERROR_MESSAGE_KEYS[error.code];
        if (key && t.has(key)) return t(key);
        return error.message;
      }
      if (error instanceof Error && error.message) return error.message;
      return t("errors.unknown");
    },
    [t],
  );
}
