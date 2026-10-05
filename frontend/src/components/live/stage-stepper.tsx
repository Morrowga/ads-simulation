"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { STEPPER, type Stage } from "@/lib/sse";
import { cn } from "@/lib/utils";

/** Analysing ad → Building audience → Customers reacting → Running simulations → Writing reasons. */
export function StageStepper({ stage, status }: { stage: string | null; status: string | null }) {
  const t = useTranslations("live.stages");
  const currentIdx = stage ? STEPPER.findIndex((s) => s.stages.includes(stage as Stage)) : -1;
  const done = status === "completed";
  return (
    <ol className="grid grid-cols-5 gap-1 sm:gap-2" aria-label={t("label")}>
      {STEPPER.map((s, i) => {
        const complete = done || (currentIdx > i && currentIdx >= 0);
        const active = !done && i === currentIdx;
        return (
          <li
            key={s.key}
            aria-current={active ? "step" : undefined}
            className={cn(
              "flex flex-col gap-1 border-t-2 pt-2 text-xs",
              complete
                ? "border-success text-foreground"
                : active
                  ? "border-primary text-primary"
                  : "border-border text-muted-foreground",
            )}
          >
            <span className="flex items-center gap-1 font-medium">
              {complete ? (
                <Check className="h-3 w-3" aria-hidden />
              ) : active ? (
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-primary" aria-hidden />
              ) : (
                <span className="tabular">{i + 1}</span>
              )}
              <span className="hidden sm:inline">{t(s.key)}</span>
            </span>
            <span className="sm:hidden">{t(`${s.key}Short`)}</span>
          </li>
        );
      })}
    </ol>
  );
}
