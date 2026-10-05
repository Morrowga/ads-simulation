"use client";

import { Check, ExternalLink, Search, Undo2, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { CursorPager, useCursorPager } from "@/components/layout/cursor-pager";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { PaymentStatusBadge } from "@/components/layout/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link } from "@/i18n/navigation";
import { formatDateTime, formatMoney, formatRelative, titleCase } from "@/lib/format";
import { useAdminMutations, useAdminPayments } from "@/lib/queries";
import type { AdminPaymentOut } from "@/lib/types";
import { cn } from "@/lib/utils";

type Action = { kind: "approve" | "cancel" | "refund"; payment: AdminPaymentOut } | null;

export default function AdminPaymentsPage() {
  const t = useTranslations("admin.payments");
  const locale = useLocale();
  const { toast } = useToast();
  const msg = useApiError();
  const [status, setStatus] = useState("pending_review");
  const [code, setCode] = useState("");
  const [query, setQuery] = useState("");
  const pager = useCursorPager();
  const payments = useAdminPayments(status === "all" ? null : status, code || null, pager.cursor);
  const m = useAdminMutations();
  const [action, setAction] = useState<Action>(null);
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [focus, setFocus] = useState(0);
  const items = useMemo(() => payments.data?.items ?? [], [payments.data]);

  // keyboard shortcuts: A approve / C cancel on the focused pending row, arrows move
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        action ||
        (e.target as HTMLElement)?.tagName === "INPUT" ||
        (e.target as HTMLElement)?.tagName === "TEXTAREA"
      )
        return;
      const row = items[focus];
      if (e.key === "ArrowDown") setFocus((f) => Math.min(items.length - 1, f + 1));
      else if (e.key === "ArrowUp") setFocus((f) => Math.max(0, f - 1));
      else if (row && row.status === "pending_review" && (e.key === "a" || e.key === "A"))
        setAction({ kind: "approve", payment: row });
      else if (row && row.status === "pending_review" && (e.key === "c" || e.key === "C"))
        setAction({ kind: "cancel", payment: row });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, focus, action]);

  const submit = async () => {
    if (!action) return;
    try {
      if (action.kind === "approve")
        await m.approve.mutateAsync({ id: action.payment.id, reference: reference || undefined });
      else if (action.kind === "cancel") await m.cancelOrder.mutateAsync({ id: action.payment.id, reason });
      else await m.refund.mutateAsync({ id: action.payment.id, reason, reference: reference || undefined });
      toast({ title: t(`done.${action.kind}`), variant: "success" });
      setAction(null);
      setReference("");
      setReason("");
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  const pendingCount = items.filter((p) => p.status === "pending_review").length;
  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <form
        className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          setCode(query.trim());
          pager.reset();
        }}
      >
        <div className="flex flex-1 flex-col gap-1.5">
          <label htmlFor="code" className="text-sm font-medium">
            {t("searchCode")}
          </label>
          <div className="flex gap-2">
            <Input
              id="code"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="ADV-…"
              className="font-mono"
            />
            <Button type="submit" variant="outline" aria-label={t("search")}>
              <Search aria-hidden />
            </Button>
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="status" className="text-sm font-medium">
            {t("status")}
          </label>
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
              <SelectItem value="pending_review">{t("statuses.pending_review")}</SelectItem>
              <SelectItem value="succeeded">{t("statuses.succeeded")}</SelectItem>
              <SelectItem value="cancelled">{t("statuses.cancelled")}</SelectItem>
              <SelectItem value="expired">{t("statuses.expired")}</SelectItem>
              <SelectItem value="refunded">{t("statuses.refunded")}</SelectItem>
              <SelectItem value="all">{t("statuses.all")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </form>
      <p className="mb-2 text-xs text-muted-foreground">{t("shortcuts", { count: pendingCount })}</p>
      {payments.isLoading ? <PageSkeleton rows={3} /> : null}
      {payments.isError ? <ErrorState error={payments.error} onRetry={() => payments.refetch()} /> : null}
      {payments.data && items.length === 0 ? (
        <EmptyState title={t("emptyTitle")} description={t("emptyBody")} />
      ) : null}
      {items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("cols.code")}</TableHead>
              <TableHead>{t("cols.user")}</TableHead>
              <TableHead>{t("cols.test")}</TableHead>
              <TableHead>{t("cols.amount")}</TableHead>
              <TableHead>{t("cols.created")}</TableHead>
              <TableHead>{t("cols.status")}</TableHead>
              <TableHead className="text-right">{t("cols.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((p, i) => (
              <TableRow
                key={p.id}
                data-state={i === focus ? "selected" : undefined}
                onClick={() => setFocus(i)}
                className={cn(i === focus && "outline outline-1 outline-primary/40")}
              >
                <TableCell className="font-mono text-xs">
                  {p.payment_code ?? "—"}
                  <span className="block text-[10px] text-muted-foreground">
                    {titleCase(p.method)} · {p.mode}
                  </span>
                </TableCell>
                <TableCell className="text-xs">{p.user_email ?? p.user_id}</TableCell>
                <TableCell className="max-w-[12rem] truncate text-xs">
                  <Link href={`/admin/tests/${p.ad_test_id}`} className="text-primary hover:underline">
                    {p.test_title ?? p.ad_test_id}
                  </Link>
                  <span className="block text-[10px] text-muted-foreground">
                    {titleCase(p.tier_code)} · {p.platform_count} {t("platforms")}
                  </span>
                </TableCell>
                <TableCell className="whitespace-nowrap tabular">
                  {p.local_currency && p.local_amount_minor !== null ? (
                    <span className="font-medium">
                      {formatMoney(p.local_amount_minor, p.local_currency, locale)}
                    </span>
                  ) : null}
                  <span className="block text-xs text-muted-foreground">
                    {formatMoney(p.amount_usd_minor, "USD", locale)}
                  </span>
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs">
                  {formatDateTime(p.created_at, locale)}
                  <span className="block text-muted-foreground">
                    {t("waiting", { time: formatRelative(p.created_at, locale) })}
                  </span>
                </TableCell>
                <TableCell>
                  <PaymentStatusBadge status={p.status} />
                  {p.flagged ? <span className="block text-[10px] text-warning">{p.flagged}</span> : null}
                  {p.cancel_reason ? (
                    <span className="block text-[10px] text-muted-foreground">{p.cancel_reason}</span>
                  ) : null}
                  {p.admin_reference ? (
                    <span className="block font-mono text-[10px] text-muted-foreground">
                      {p.admin_reference}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    {p.status === "pending_review" ? (
                      <>
                        <Button size="sm" onClick={() => setAction({ kind: "approve", payment: p })}>
                          <Check aria-hidden /> {t("approve")}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setAction({ kind: "cancel", payment: p })}
                        >
                          <X aria-hidden /> {t("cancel")}
                        </Button>
                      </>
                    ) : null}
                    {p.status === "succeeded" && p.method !== "trial" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setAction({ kind: "refund", payment: p })}
                      >
                        <Undo2 aria-hidden /> {t("refund")}
                      </Button>
                    ) : null}
                    {p.stripe_payment_intent_id ? (
                      <Button size="sm" variant="ghost" asChild>
                        <a
                          href={`https://dashboard.stripe.com/${p.mode === "stripe_live" ? "" : "test/"}payments/${p.stripe_payment_intent_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={t("stripeLink")}
                        >
                          <ExternalLink aria-hidden />
                        </a>
                      </Button>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <CursorPager pager={pager} nextCursor={payments.data?.next_cursor} />

      <Dialog open={!!action} onOpenChange={(o) => !o && setAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{action ? t(`dialog.${action.kind}.title`) : ""}</DialogTitle>
            <DialogDescription>
              {action
                ? t(`dialog.${action.kind}.body`, {
                    code: action.payment.payment_code ?? action.payment.id,
                    amount:
                      action.payment.local_currency && action.payment.local_amount_minor !== null
                        ? formatMoney(
                            action.payment.local_amount_minor,
                            action.payment.local_currency,
                            locale,
                          )
                        : formatMoney(action.payment.amount_usd_minor, "USD", locale),
                  })
                : ""}
            </DialogDescription>
          </DialogHeader>
          {action?.kind !== "cancel" ? (
            <FormField id="reference" label={t("dialog.reference")} help={t("dialog.referenceHelp")}>
              <Input
                id="reference"
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                maxLength={120}
              />
            </FormField>
          ) : null}
          {action?.kind !== "approve" ? (
            <FormField id="reason" label={t("dialog.reason")} required>
              <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} />
            </FormField>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAction(null)}>
              {t("dialog.close")}
            </Button>
            <Button
              variant={action?.kind === "approve" ? "default" : "destructive"}
              onClick={submit}
              loading={m.approve.isPending || m.cancelOrder.isPending || m.refund.isPending}
              disabled={action?.kind !== "approve" && !reason.trim()}
            >
              {action ? t(`dialog.${action.kind}.confirm`) : ""}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
