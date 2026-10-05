"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { formatMoney, titleCase } from "@/lib/format";
import { useAdminMutations, useAdminPrices } from "@/lib/queries";
import type { PriceItemOut } from "@/lib/api-types-extra";

export default function AdminPricesPage() {
  const t = useTranslations("admin.prices");
  const locale = useLocale();
  const { toast } = useToast();
  const prices = useAdminPrices();
  const m = useAdminMutations();
  const [items, setItems] = useState<PriceItemOut[]>([]);
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (prices.data) setItems(prices.data.items);
  }, [prices.data]);
  if (prices.isLoading) return <PageSkeleton />;
  if (prices.isError || !prices.data)
    return <ErrorState error={prices.error} onRetry={() => prices.refetch()} />;

  const update = (code: string, patch: Partial<PriceItemOut>) =>
    setItems((list) => list.map((x) => (x.tier_code === code ? { ...x, ...patch } : x)));
  const save = async () => {
    setError(null);
    try {
      await m.putPrices.mutateAsync({
        items: items.map((x) => ({
          tier_code: x.tier_code,
          amount_minor: x.amount_minor,
          extra_platform_minor: x.extra_platform_minor,
          active: x.active,
        })),
        change_note: note || t("defaultNote"),
      });
      toast({ title: t("saved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };
  return (
    <>
      <PageHeader title={t("title")} description={t("description", { currency: prices.data.currency })} />
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("tier")}</TableHead>
            <TableHead>{t("amount")}</TableHead>
            <TableHead>{t("extra")}</TableHead>
            <TableHead>{t("active")}</TableHead>
            <TableHead className="text-right">{t("preview")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((x) => (
            <TableRow key={x.tier_code}>
              <TableCell className="font-medium">{titleCase(x.tier_code)}</TableCell>
              <TableCell>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={x.amount_minor}
                  aria-label={t("amountFor", { tier: x.tier_code })}
                  onChange={(e) => update(x.tier_code, { amount_minor: Number(e.target.value) })}
                  className="w-32"
                />
              </TableCell>
              <TableCell>
                <Input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={x.extra_platform_minor}
                  aria-label={t("extraFor", { tier: x.tier_code })}
                  onChange={(e) => update(x.tier_code, { extra_platform_minor: Number(e.target.value) })}
                  className="w-32"
                />
              </TableCell>
              <TableCell>
                <Switch
                  checked={x.active}
                  onCheckedChange={(v) => update(x.tier_code, { active: v })}
                  aria-label={t("activeFor", { tier: x.tier_code })}
                />
              </TableCell>
              <TableCell className="text-right tabular">
                {formatMoney(x.amount_minor, x.currency, locale)}{" "}
                <span className="text-muted-foreground">
                  + {formatMoney(x.extra_platform_minor, x.currency, locale)}
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-2 text-xs text-muted-foreground">{t("minorHint")}</p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <FormField id="note" label={t("changeNote")} className="flex-1">
          <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
        </FormField>
        <Button onClick={save} loading={m.putPrices.isPending}>
          {t("save")}
        </Button>
      </div>
      <InlineError error={error} />
    </>
  );
}
