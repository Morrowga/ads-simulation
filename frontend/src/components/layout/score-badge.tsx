"use client";

import { useTranslations } from "next-intl";
import { scoreBand } from "@/lib/format";
import { cn } from "@/lib/utils";

const BAND_CLASS = {
  weak: "bg-danger-bg text-danger",
  below: "bg-warning-bg text-warning",
  average: "bg-neutral-bg text-neutral",
  good: "bg-success-bg text-success",
  strong: "bg-success-bg text-success",
  none: "bg-neutral-bg text-neutral",
} as const;

/** Score 0–100: red / amber / green, always with the number and a text label (never colour alone). */
export function ScoreBadge({
  score,
  size = "sm",
  provisional = false,
  className,
}: {
  score: number | null | undefined;
  size?: "sm" | "lg" | "xl";
  provisional?: boolean;
  className?: string;
}) {
  const t = useTranslations("score");
  const band = scoreBand(score);
  const label = band === "none" ? t("none") : t(band);
  if (size === "sm") {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium tabular",
          BAND_CLASS[band],
          className,
        )}
        aria-label={`${t("score")} ${score ?? "—"} ${label}`}
      >
        <span className="font-semibold">
          {score === null || score === undefined ? "—" : Math.round(score)}
        </span>
        <span>{label}</span>
      </span>
    );
  }
  return (
    <div
      className={cn("inline-flex flex-col items-center rounded-xl px-6 py-4", BAND_CLASS[band], className)}
      aria-label={`${t("score")} ${score ?? "—"} ${label}`}
    >
      <span
        className={cn("font-bold tabular leading-none", size === "xl" ? "text-6xl sm:text-7xl" : "text-4xl")}
      >
        {score === null || score === undefined ? "—" : Math.round(score)}
      </span>
      <span className="mt-2 text-sm font-medium">
        {label}
        {provisional ? ` · ${t("provisional")}` : ""}
      </span>
    </div>
  );
}
