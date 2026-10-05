"use client";

import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useApiError } from "@/hooks/use-api-error";

export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const t = useTranslations("common");
  const msg = useApiError();
  return (
    <Alert variant="destructive">
      <AlertTriangle aria-hidden />
      <AlertTitle>{title ?? t("somethingWrong")}</AlertTitle>
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>{msg(error)}</span>
        {onRetry ? (
          <Button size="sm" variant="outline" onClick={onRetry}>
            {t("retry")}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

export function InlineError({ error }: { error: unknown }) {
  const msg = useApiError();
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-danger">
      {msg(error)}
    </p>
  );
}
