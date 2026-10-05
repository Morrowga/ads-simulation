"use client";

import { useLocale, useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber, formatPercent, rangeText, scoreBand } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TypedReport } from "./report-types";

const TONE: Record<string, string> = {
  weak: "border-danger/40 bg-danger-bg text-danger",
  below: "border-warning/40 bg-warning-bg text-warning",
  average: "border-border bg-muted text-foreground",
  good: "border-success/40 bg-success-bg text-success",
  strong: "border-success/40 bg-success-bg text-success",
  none: "border-border bg-muted text-foreground",
};

/** What an owner expects to see: verdict, expected result, what happened, top reasons. */
export function OverviewPanel({ report, goal }: { report: TypedReport; goal: string }) {
  const t = useTranslations("report.overview");
  const tb = useTranslations("report.blockers.kinds");
  const locale = useLocale();
  const score = report.raw.score;
  const band = scoreBand(score);

  // expected result for the goal, as a range of people
  const hp = report.headline.estimated_people ?? {};
  const range = report.headline.value
    ? rangeText(
        {
          p10: hp.p10 ?? report.headline.value.p10,
          p50: hp.p50 ?? report.headline.value.p50,
          p90: hp.p90 ?? report.headline.value.p90,
        },
        (v) => formatNumber(v, locale),
      )
    : "—";

  // out of every 100 people who saw the ad
  const f = report.funnel;
  const seen = Math.max(1, Number(f.seen ?? 0));
  const convKey = goal === "messages" ? "messaged" : "bought";
  const showConv = goal === "sales" || goal === "messages";
  const steps = [
    { label: t("stopped"), v: Number(f.stopped ?? 0) },
    { label: t("clicked"), v: Number(f.clicked ?? 0) },
    ...(showConv ? [{ label: t(convKey), v: Number(f[convKey] ?? 0) }] : []),
  ];

  // most common reason people who clicked did not convert
  const blockers: Record<string, number> = {};
  for (const p of report.platforms)
    for (const [k, v] of Object.entries(p.blockers ?? {})) blockers[k] = (blockers[k] ?? 0) + v.count;
  const bSum = Object.values(blockers).reduce((a, x) => a + x, 0);
  const topBlocker = Object.entries(blockers).sort((a, b) => b[1] - a[1])[0];

  // up to three plain reasons: general first, then the rest
  const all = report.raw.reasons;
  const reasons = [...all.filter((x) => x.section === "general"), ...all.filter((x) => x.section !== "general")].slice(
    0,
    3,
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Card className={cn("border", TONE[band])}>
          <CardContent className="space-y-1 p-6">
            <p className="text-xs font-medium uppercase tracking-wide opacity-80">{t("verdictTitle")}</p>
            <p className="text-xl font-semibold">{t(`verdict.${band}` as never)}</p>
            <p className="text-sm opacity-90">{t(`verdictBody.${band}` as never)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-1 p-6">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t("expectedTitle")}
            </p>
            <p className="text-3xl font-semibold tabular">{range}</p>
            <p className="text-sm text-muted-foreground">
              {t("expectedBody", { goal: report.headline.label.toLowerCase() })}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("per100Title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.map((s) => {
            const share = s.v / seen;
            return (
              <div key={s.label} className="space-y-1">
                <div className="flex items-baseline justify-between text-sm">
                  <span>{s.label}</span>
                  <span className="font-medium tabular">{t("per100", { n: Math.round(share * 100 * 10) / 10 })}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(1, share * 100)}%` }} />
                </div>
              </div>
            );
          })}
          {showConv && topBlocker && bSum > 0 ? (
            <p className="pt-1 text-sm text-muted-foreground">
              {t("topBlocker", {
                reason: tb(topBlocker[0] as never),
                pct: formatPercent(topBlocker[1] / bSum, 0, locale),
              })}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {reasons.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("reasonsTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {reasons.map((x, i) => (
                <li key={i} className="flex gap-3 text-sm">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                    {i + 1}
                  </span>
                  <span>{x.statement}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}