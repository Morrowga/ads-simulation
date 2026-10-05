"use client";

import { Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { CursorPager, useCursorPager } from "@/components/layout/cursor-pager";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { ScoreBadge } from "@/components/layout/score-badge";
import { StatusBadge } from "@/components/layout/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatDateTime, formatNumber, titleCase } from "@/lib/format";
import { useAdminTests } from "@/lib/queries";
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

export default function AdminTestsPage() {
  const t = useTranslations("admin.tests");
  const ts = useTranslations("status.test");
  const locale = useLocale();
  const [status, setStatus] = useState("all");
  const [email, setEmail] = useState("");
  const [query, setQuery] = useState("");
  const pager = useCursorPager();
  const tests = useAdminTests(status === "all" ? null : status, email || null, pager.cursor);
  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <form
        className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          setEmail(query.trim());
          pager.reset();
        }}
      >
        <FormField id="email" label={t("searchEmail")} className="flex-1">
          <div className="flex gap-2">
            <Input id="email" value={query} onChange={(e) => setQuery(e.target.value)} />
            <Button type="submit" variant="outline" aria-label={t("search")}>
              <Search aria-hidden />
            </Button>
          </div>
        </FormField>
        <FormField id="status" label={t("status")}>
          <Select
            value={status}
            onValueChange={(v) => {
              setStatus(v);
              pager.reset();
            }}
          >
            <SelectTrigger id="status" className="sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("all")}</SelectItem>
              {STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {ts(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      </form>
      {tests.isLoading ? <PageSkeleton rows={3} /> : null}
      {tests.isError ? <ErrorState error={tests.error} onRetry={() => tests.refetch()} /> : null}
      {tests.data && tests.data.items.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {tests.data && tests.data.items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("cols.test")}</TableHead>
              <TableHead>{t("cols.user")}</TableHead>
              <TableHead>{t("cols.status")}</TableHead>
              <TableHead>{t("cols.score")}</TableHead>
              <TableHead className="text-right">{t("cols.cost")}</TableHead>
              <TableHead>{t("cols.created")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tests.data.items.map((x) => (
              <TableRow key={x.id}>
                <TableCell>
                  <Link href={`/admin/tests/${x.id}`} className="font-medium text-primary hover:underline">
                    {x.title}
                  </Link>
                  <span className="block text-xs text-muted-foreground">
                    {titleCase(x.tier_code)} · {titleCase(x.post_type)} · {titleCase(x.goal)} ·{" "}
                    {x.platforms.map(titleCase).join(", ")} · {x.country_code} · {x.paid_via ?? "—"}
                  </span>
                </TableCell>
                <TableCell className="text-xs">{x.user_email ?? x.user_id}</TableCell>
                <TableCell>
                  <StatusBadge status={x.status} />
                  {x.status === "running" ? (
                    <span className="block text-xs tabular text-muted-foreground">
                      {x.progress_pct}% · {x.stage}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell>{x.score !== null ? <ScoreBadge score={x.score} /> : "—"}</TableCell>
                <TableCell className="text-right tabular">${formatNumber(x.cost_usd, locale, 4)}</TableCell>
                <TableCell className="whitespace-nowrap text-xs">
                  {formatDateTime(x.created_at, locale)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <CursorPager pager={pager} nextCursor={tests.data?.next_cursor} />
    </>
  );
}
