"use client";

import { CreditCard } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { CursorPager, useCursorPager } from "@/components/layout/cursor-pager";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { Money } from "@/components/layout/money";
import { PageHeader } from "@/components/layout/page-header";
import { PaymentStatusBadge } from "@/components/layout/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { formatDateTime, formatMoney } from "@/lib/format";
import { usePayments } from "@/lib/queries";

export default function PaymentsPage() {
  const t = useTranslations("payments");
  const locale = useLocale();
  const pager = useCursorPager();
  const payments = usePayments(pager.cursor);
  const pending = (payments.data?.items ?? []).filter((p) => p.status === "pending_review");

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      {pending.length > 0 ? (
        <Alert variant="warning" className="mb-4">
          <AlertDescription>{t("awaitingApproval", { count: pending.length })}</AlertDescription>
        </Alert>
      ) : null}
      {payments.isLoading ? <PageSkeleton rows={3} /> : null}
      {payments.isError ? <ErrorState error={payments.error} onRetry={() => payments.refetch()} /> : null}
      {payments.data && payments.data.items.length === 0 ? (
        <EmptyState icon={CreditCard} title={t("emptyTitle")} description={t("emptyBody")} />
      ) : null}
      {payments.data && payments.data.items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("date")}</TableHead>
              <TableHead>{t("method")}</TableHead>
              <TableHead>{t("amount")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("reference")}</TableHead>
              <TableHead className="text-right">{t("test")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {payments.data.items.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="whitespace-nowrap tabular">
                  {formatDateTime(p.created_at, locale)}
                </TableCell>
                <TableCell>
                  {t(`methods.${p.method}`)}
                  {p.mode === "test" ? (
                    <span className="ml-1 text-xs text-muted-foreground">({t("testMode")})</span>
                  ) : null}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {p.method === "manual" && p.local_currency && p.local_amount_minor !== null ? (
                    <span className="tabular">
                      {formatMoney(p.local_amount_minor, p.local_currency, locale)}{" "}
                      <span className="text-muted-foreground">
                        ({formatMoney(p.amount_usd_minor, "USD", locale)})
                      </span>
                    </span>
                  ) : (
                    <Money usdMinor={p.amount_usd_minor} />
                  )}
                </TableCell>
                <TableCell>
                  <PaymentStatusBadge status={p.status} />
                  {p.cancel_reason ? (
                    <p className="mt-1 text-xs text-muted-foreground">{p.cancel_reason}</p>
                  ) : null}
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {p.payment_code ?? p.admin_reference ?? "—"}
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild variant="link" size="sm">
                    <Link href={`/tests/${p.ad_test_id}`}>{t("openTest")}</Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <CursorPager pager={pager} nextCursor={payments.data?.next_cursor} />
    </>
  );
}
