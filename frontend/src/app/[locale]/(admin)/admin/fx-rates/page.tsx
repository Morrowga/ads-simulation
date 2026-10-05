"use client";

import { Plus, Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { formatDateTime } from "@/lib/format";
import { useAdminFxRates, useAdminMutations } from "@/lib/queries";
import type { FxRateIn } from "@/lib/api-types-extra";

export default function AdminFxRatesPage() {
  const t = useTranslations("admin.fx");
  const locale = useLocale();
  const { toast } = useToast();
  const rates = useAdminFxRates();
  const m = useAdminMutations();
  const [rows, setRows] = useState<(FxRateIn & { updated_at?: string })[]>([]);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (rates.data)
      setRows(
        rates.data.map((r) => ({
          currency: r.currency,
          rate_per_usd: r.rate_per_usd,
          effective_date: r.effective_date,
          note: r.note,
          updated_at: r.updated_at,
        })),
      );
  }, [rates.data]);
  if (rates.isLoading) return <PageSkeleton />;
  if (rates.isError) return <ErrorState error={rates.error} onRetry={() => rates.refetch()} />;

  const update = (i: number, patch: Partial<FxRateIn>) =>
    setRows((list) => list.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const save = async () => {
    setError(null);
    try {
      await m.putFxRates.mutateAsync({
        rates: rows.map((r) => ({
          currency: r.currency.toUpperCase(),
          rate_per_usd: r.rate_per_usd,
          effective_date: r.effective_date || null,
          note: r.note ?? "",
        })),
      });
      toast({ title: t("saved"), variant: "success" });
    } catch (e) {
      setError(e);
    }
  };
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button
            variant="outline"
            onClick={() =>
              setRows([
                ...rows,
                {
                  currency: "",
                  rate_per_usd: 1,
                  effective_date: new Date().toISOString().slice(0, 10),
                  note: "",
                },
              ])
            }
          >
            <Plus aria-hidden /> {t("add")}
          </Button>
        }
      />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("currency")}</TableHead>
            <TableHead>{t("rate")}</TableHead>
            <TableHead>{t("date")}</TableHead>
            <TableHead>{t("note")}</TableHead>
            <TableHead>{t("updated")}</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => (
            <TableRow key={i}>
              <TableCell>
                <Input
                  value={r.currency}
                  maxLength={3}
                  aria-label={t("currency")}
                  onChange={(e) => update(i, { currency: e.target.value.toUpperCase() })}
                  className="w-24 font-mono"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  step="any"
                  min={0}
                  value={r.rate_per_usd}
                  aria-label={t("rateFor", { currency: r.currency })}
                  onChange={(e) => update(i, { rate_per_usd: Number(e.target.value) })}
                  className="w-36"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="date"
                  value={r.effective_date ?? ""}
                  aria-label={t("date")}
                  onChange={(e) => update(i, { effective_date: e.target.value })}
                  className="w-40"
                />
              </TableCell>
              <TableCell>
                <Input
                  value={r.note ?? ""}
                  aria-label={t("note")}
                  onChange={(e) => update(i, { note: e.target.value })}
                />
              </TableCell>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                {r.updated_at ? formatDateTime(r.updated_at, locale) : t("new")}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("remove")}
                  onClick={() => setRows(rows.filter((_x, j) => j !== i))}
                >
                  <Trash2 aria-hidden />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-muted-foreground">{t("hint")}</p>
      <div className="mt-4">
        <Button
          onClick={save}
          loading={m.putFxRates.isPending}
          disabled={rows.some((r) => r.currency.length !== 3)}
        >
          {t("save")}
        </Button>
      </div>
      <InlineError error={error} />
    </>
  );
}
