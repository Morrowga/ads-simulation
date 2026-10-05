"use client";

import { FlaskConical, Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { CursorPager, useCursorPager } from "@/components/layout/cursor-pager";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { ScoreBadge } from "@/components/layout/score-badge";
import { StatusBadge } from "@/components/layout/status-badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Link } from "@/i18n/navigation";
import { formatDate, titleCase } from "@/lib/format";
import { useTests } from "@/lib/queries";
import { testHref } from "@/lib/test-routes";
import type { TestStatus } from "@/lib/types";

const STATUSES: TestStatus[] = [
  "draft",
  "awaiting_payment",
  "payment_review",
  "queued",
  "running",
  "completed",
  "failed",
  "refunded",
];

export function TestList() {
  const t = useTranslations("dashboard");
  const ts = useTranslations("status.test");
  const locale = useLocale();
  const [status, setStatus] = useState<string>("all");
  const pager = useCursorPager();
  const tests = useTests(pager.cursor, status === "all" ? undefined : status);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">{t("yourTests")}</h2>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            pager.reset();
          }}
        >
          <SelectTrigger className="w-48" aria-label={t("filterStatus")}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {ts(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {tests.isLoading ? <PageSkeleton rows={3} /> : null}
      {tests.isError ? <ErrorState error={tests.error} onRetry={() => tests.refetch()} /> : null}
      {tests.data && tests.data.items.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title={status === "all" ? t("emptyTitle") : t("emptyFiltered")}
          description={status === "all" ? t("emptyBody") : undefined}
          action={
            status === "all" ? (
              <Button asChild>
                <Link href="/tests/new">
                  <Plus aria-hidden /> {t("newTest")}
                </Link>
              </Button>
            ) : undefined
          }
        />
      ) : null}
      {tests.data && tests.data.items.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {tests.data.items.map((item) => (
            <li key={item.id}>
              <Link
                href={testHref(item.id, item.status)}
                className="flex flex-col gap-2 p-4 hover:bg-muted/40 sm:flex-row sm:items-center sm:gap-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{item.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {titleCase(item.tier_code)} · {titleCase(item.post_type)} · {titleCase(item.goal)} ·{" "}
                    {item.platforms.map(titleCase).join(", ")} · {item.country_code}
                  </p>
                  {item.status === "running" || item.status === "queued" ? (
                    <div className="mt-2 flex items-center gap-2">
                      <Progress
                        value={item.progress_pct}
                        className="h-1.5 max-w-xs"
                        aria-label={t("progress", { pct: item.progress_pct })}
                      />
                      <span className="text-xs tabular text-muted-foreground">{item.progress_pct}%</span>
                    </div>
                  ) : null}
                </div>
                <div className="flex items-center gap-3 sm:justify-end">
                  {item.score !== null ? <ScoreBadge score={item.score} /> : null}
                  <StatusBadge status={item.status} />
                  <span className="text-xs text-muted-foreground tabular">
                    {formatDate(item.finished_at ?? item.created_at, locale)}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
      <CursorPager pager={pager} nextCursor={tests.data?.next_cursor} />
    </div>
  );
}
