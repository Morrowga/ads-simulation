"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatCard } from "@/components/admin/stat-card";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Link } from "@/i18n/navigation";
import { formatMoney, formatNumber, formatPercent, titleCase } from "@/lib/format";
import { useAdminMetrics } from "@/lib/queries";
import { prefersReducedMotion } from "@/lib/utils";

export default function AdminOverviewPage() {
  const t = useTranslations("admin.overview");
  const locale = useLocale();
  const [days, setDays] = useState(30);
  const metrics = useAdminMetrics(days);
  if (metrics.isLoading) return <PageSkeleton />;
  if (metrics.isError || !metrics.data)
    return <ErrorState error={metrics.error} onRetry={() => metrics.refetch()} />;
  const mdata = metrics.data;
  const perDay = (mdata.tests_per_day as { day: string; count: number }[]).map((d) => ({
    day: d.day.slice(5),
    count: d.count,
  }));
  const usd = (v: number) => `$${formatNumber(v, locale, 2)}`;
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <SelectTrigger className="w-36" aria-label={t("period")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[1, 7, 30, 90].map((d) => (
                <SelectItem key={d} value={String(d)}>
                  {t("days", { count: d })}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("revenue")}
          value={formatMoney(mdata.revenue_total_usd_minor, "USD", locale)}
          hint={Object.entries(mdata.revenue_by_method)
            .map(([k, v]) => `${titleCase(k)}: ${formatMoney(v, "USD", locale)}`)
            .join(" · ")}
        />
        <StatCard
          label={t("aiCost")}
          value={usd(mdata.ai_cost_usd)}
          hint={t("llmToday", { spend: usd(mdata.llm_spend_today_usd), cap: usd(mdata.llm_daily_cap_usd) })}
        />
        <StatCard
          label={t("margin")}
          value={usd(mdata.gross_margin_usd)}
          hint={
            mdata.gross_margin_pct !== null ? formatPercent(mdata.gross_margin_pct / 100, 1, locale) : "—"
          }
        />
        <StatCard
          label={t("tests")}
          value={formatNumber(mdata.completed_tests, locale)}
          hint={t("failed", { count: mdata.failed_tests })}
        />
        <StatCard
          label={t("pending")}
          value={formatNumber(mdata.pending_manual_orders, locale)}
          hint={
            <Link href="/admin/payments" className="text-primary hover:underline">
              {t("openQueue")}
            </Link>
          }
        />
        <StatCard
          label={t("approval")}
          value={
            mdata.average_approval_time_min !== null
              ? t("minutes", { n: formatNumber(mdata.average_approval_time_min, locale, 0) })
              : "—"
          }
        />
      </div>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>{t("perDay")}</CardTitle>
        </CardHeader>
        <CardContent>
          {perDay.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noTests")}</p>
          ) : (
            <div style={{ height: 220 }} role="img" aria-label={t("perDay")}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perDay}>
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                    width={32}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "var(--foreground)",
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill="var(--chart-1)"
                    radius={[4, 4, 0, 0]}
                    isAnimationActive={!prefersReducedMotion()}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
      <div className="mt-6 flex flex-wrap gap-2">
        <Button asChild variant="outline">
          <Link href="/admin/tests">{t("goTests")}</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/admin/users">{t("goUsers")}</Link>
        </Button>
      </div>
    </>
  );
}
