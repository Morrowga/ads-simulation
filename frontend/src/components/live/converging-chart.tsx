"use client";

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPercent } from "@/lib/format";
import type { ChartPoint } from "@/lib/sse";
import { prefersReducedMotion } from "@/lib/utils";

/** P10–P90 band and P50 line of the click rate vs. runs done; the band narrows as runs accumulate. */
export function ConvergingChart({ points, height = 220 }: { points: ChartPoint[]; height?: number }) {
  const t = useTranslations("live.chart");
  const locale = useLocale();
  const data = useMemo(
    () =>
      points.map((p) => ({
        run: p.run,
        p10: p.p10,
        band: Math.max(0, p.p90 - p.p10),
        p50: p.p50,
        p90: p.p90,
      })),
    [points],
  );
  const animate = !prefersReducedMotion();
  if (data.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-md border border-dashed border-border text-sm text-muted-foreground"
        style={{ height }}
      >
        {t("waiting")}
      </div>
    );
  }
  return (
    <figure>
      <div
        style={{ height }}
        role="img"
        aria-label={t("aria", {
          runs: data[data.length - 1].run,
          p50: formatPercent(data[data.length - 1].p50, 2, locale),
        })}
      >
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <XAxis dataKey="run" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" tickLine={false} />
            <YAxis
              tickFormatter={(v: number) => formatPercent(v, 1, locale)}
              tick={{ fontSize: 11 }}
              stroke="var(--muted-foreground)"
              tickLine={false}
              width={48}
            />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
                color: "var(--foreground)",
              }}
              labelFormatter={(label) => t("run", { n: String(label ?? "") })}
              formatter={(value, name, item) => {
                const v = typeof value === "number" ? value : Number(value ?? 0);
                if (name === "band") {
                  const row = (item as { payload?: { p10: number; p90: number } }).payload;
                  return [
                    row ? `${formatPercent(row.p10, 2, locale)} – ${formatPercent(row.p90, 2, locale)}` : "—",
                    t("range"),
                  ];
                }
                if (name === "p10") return [formatPercent(v, 2, locale), "P10"];
                return [formatPercent(v, 2, locale), t("median")];
              }}
            />
            <Area
              type="monotone"
              dataKey="p10"
              stackId="band"
              stroke="none"
              fill="transparent"
              isAnimationActive={animate}
            />
            <Area
              type="monotone"
              dataKey="band"
              stackId="band"
              stroke="none"
              fill="var(--chart-band)"
              isAnimationActive={animate}
            />
            <Line
              type="monotone"
              dataKey="p50"
              stroke="var(--primary)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={animate}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-muted-foreground">{t("caption")}</figcaption>
    </figure>
  );
}
