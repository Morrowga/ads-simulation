"use client";

import { useLocale, useTranslations } from "next-intl";
import { useAnimatedNumber } from "@/hooks/use-animated-number";
import { formatNumber } from "@/lib/format";

export const FUNNEL_STEPS = [
  "seen",
  "skipped",
  "stopped",
  "reacted",
  "commented",
  "clicked",
  "bought",
] as const;

function Counter({ label, value }: { label: string; value: number }) {
  const locale = useLocale();
  const shown = useAnimatedNumber(value, 450);
  return (
    <div className="rounded-md border border-border p-3 text-center">
      <p className="text-lg font-semibold tabular sm:text-xl">{formatNumber(Math.round(shown), locale)}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

/** Seen → Skipped → Stopped → Reacted → Commented → Clicked → Bought with a count-up between batches. */
export function FunnelCounters({ funnel, goal }: { funnel: Record<string, number>; goal?: string | null }) {
  const t = useTranslations("live.funnel");
  const steps = [...FUNNEL_STEPS] as string[];
  if (goal === "messages") steps.splice(steps.indexOf("bought"), 1, "messaged");
  return (
    <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
      {steps.map((k) => (
        <Counter key={k} label={t(k as never)} value={Number(funnel[k] ?? 0)} />
      ))}
    </div>
  );
}
