"use client";

import { useLocale, useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { BatchEvent } from "@/lib/sse";

/** One card per batch of runs: run numbers, scenario chips, score and click rate. */
export function RunFeed({ batches, max = 12 }: { batches: BatchEvent[]; max?: number }) {
  const t = useTranslations("live.feed");
  const locale = useLocale();
  if (batches.length === 0) return <p className="text-sm text-muted-foreground">{t("waiting")}</p>;
  return (
    <ul className="space-y-2" aria-label={t("label")}>
      {batches.slice(0, max).map((b) => {
        const runs = b.batch.map((r) => r.run);
        const lo = Math.min(...runs);
        const hi = Math.max(...runs);
        const scenarios = Array.from(new Set(b.batch.map((r) => r.scenario)));
        const scores = b.batch.map((r) => r.score).filter((x): x is number => x !== null);
        const avgScore = scores.length ? scores.reduce((a, x) => a + x, 0) / scores.length : null;
        const ctrs = b.batch.map((r) => r.ctr).filter((x): x is number => x !== null);
        const avgCtr = ctrs.length ? ctrs.reduce((a, x) => a + x, 0) / ctrs.length : null;
        return (
          <li
            key={`${b.platform}-${b.audience_idx}-${b.runs_done}`}
            className="rounded-md border border-border p-3 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium tabular">
                {lo === hi ? t("run", { n: lo }) : t("runs", { from: lo, to: hi })}
              </span>
              <span className="text-xs text-muted-foreground">
                {titleCase(b.platform)}
                {b.audience_idx > 0 ? ` · ${t("audience", { n: b.audience_idx + 1 })}` : ""}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {scenarios.map((s) => (
                <Badge key={s} variant="neutral">
                  {titleCase(s)}
                </Badge>
              ))}
              <span className="ml-auto text-xs tabular text-muted-foreground">
                {avgScore !== null ? `${t("score")} ${formatNumber(avgScore, locale, 0)}` : ""}
                {avgCtr !== null ? ` · ${t("ctr")} ${formatPercent(avgCtr, 2, locale)}` : ""}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
