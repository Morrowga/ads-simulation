"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import type { PaymentStatus, TestStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TEST_VARIANT: Record<TestStatus, "success" | "warning" | "danger" | "neutral" | "info"> = {
  draft: "neutral",
  awaiting_payment: "warning",
  payment_review: "warning",
  queued: "info",
  running: "info",
  completed: "success",
  failed: "danger",
  refunded: "neutral",
};

/** Status chip: green / amber / red / grey; `running` uses the primary accent (design system 11). */
export function StatusBadge({ status, className }: { status: TestStatus; className?: string }) {
  const t = useTranslations("status.test");
  const running = status === "running" || status === "queued";
  return (
    <Badge
      variant={running ? "info" : TEST_VARIANT[status]}
      className={cn(running && "border-primary/30", className)}
    >
      {running ? (
        <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-primary animate-pulse" aria-hidden />
      ) : null}
      {t(status)}
    </Badge>
  );
}

const PAY_VARIANT: Record<PaymentStatus, "success" | "warning" | "danger" | "neutral"> = {
  pending: "warning",
  pending_review: "warning",
  succeeded: "success",
  failed: "danger",
  cancelled: "neutral",
  expired: "neutral",
  refunded: "neutral",
  consumed: "neutral",
};

export function PaymentStatusBadge({ status, className }: { status: PaymentStatus; className?: string }) {
  const t = useTranslations("status.payment");
  return (
    <Badge variant={PAY_VARIANT[status]} className={className}>
      {t(status)}
    </Badge>
  );
}

export function PlatformStatusBadge({ status }: { status: "full" | "beta" | "planned" }) {
  const t = useTranslations("status.platform");
  if (status === "full") return null;
  return <Badge variant={status === "beta" ? "warning" : "neutral"}>{t(status)}</Badge>;
}
