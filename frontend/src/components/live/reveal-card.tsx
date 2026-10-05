"use client";

import { ImageUp, CheckCircle2, Cpu } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

const LAST_STEP = 8; // 4 nodes + 3 connectors, then the actions

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "text-success",
  good: "text-success",
  medium: "text-warning",
  building: "text-destructive",
  low: "text-destructive",
};

function scoreTone(score: number | null) {
  if (score === null) return "bg-muted text-muted-foreground";
  if (score >= 70) return "bg-success/15 text-success";
  if (score >= 40) return "bg-warning/15 text-warning";
  return "bg-destructive/15 text-destructive";
}

function Node({ visible, label, children }: { visible: boolean; label: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "relative h-16 w-16 shrink-0 transition-all duration-500 motion-reduce:transition-none",
        visible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
      )}
    >
      {children}
      <span className="absolute left-1/2 top-full mt-2 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-muted-foreground">
        {label}
      </span>
    </div>
  );
}

function Connector({ visible }: { visible: boolean }) {
  // 31px + 2px line = centred on the 64px node boxes
  return (
    <div className="mt-[31px] h-0.5 min-w-4 flex-1 overflow-hidden">
      <div
        className={cn(
          "h-full w-full origin-left bg-primary/40 transition-transform duration-500 motion-reduce:transition-none",
          visible ? "scale-x-100" : "scale-x-0",
        )}
      />
    </div>
  );
}

export function RevealCard({
  runs,
  score,
  confidence,
  reportHref,
}: {
  runs: number;
  score: number | null;
  confidence: string;
  reportHref: string;
}) {
  const t = useTranslations("live");
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setStep(LAST_STEP);
      return;
    }
    const iv = setInterval(() => {
      setStep((s) => {
        if (s >= LAST_STEP) {
          clearInterval(iv);
          return s;
        }
        return s + 1;
      });
    }, 500);
    return () => clearInterval(iv);
  }, []);

  const node = (i: number) => step >= 2 * i + 1;
  const conn = (i: number) => step >= 2 * i + 2;
  const showActions = step >= LAST_STEP;
  const rounded = score !== null ? Math.round(score) : null;

  return (
    <Card className="mx-auto max-w-3xl border-0 shadow-none">
      <CardContent className="space-y-10 p-6 sm:p-8">
        {/* top-left: icon + text on one line */}
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-6 w-6 shrink-0 text-success" aria-hidden />
          <p className="text-lg font-semibold" aria-live="polite">
            {t("revealRuns", { runs })}
          </p>
        </div>

        {/* node animation: centred */}
        <div className="mx-auto flex w-full max-w-md items-start pb-8">
          <Node visible={node(0)} label={t("revealNodes.advar")}>
            <span className="flex h-full w-full items-center justify-center rounded-md bg-primary text-2xl font-bold text-primary-foreground">
              A
            </span>
          </Node>
          <Connector visible={conn(0)} />
          <Node visible={node(1)} label={t("revealNodes.engine")}>
            <span className="flex h-full w-full items-center justify-center rounded-md bg-[#59534c] text-white">
              <Cpu className="h-7 w-7" aria-hidden />
            </span>
          </Node>
          <Connector visible={conn(1)} />
          <Node visible={node(2)} label={t("revealNodes.ad")}>
            <span className="flex h-full w-full items-center justify-center rounded-md bg-[#e6332e] text-white">
              <ImageUp className="h-7 w-7" aria-hidden />
            </span>
          </Node>
          <Connector visible={conn(2)} />
          <Node visible={node(3)} label={t("revealNodes.score")}>
            <span
              className={cn(
                "flex h-full w-full items-center justify-center rounded-md text-2xl font-bold tabular",
                scoreTone(rounded),
              )}
            >
              {rounded ?? "—"}
            </span>
          </Node>
        </div>

        {/* next line, right end: confidence + open report */}
        <div
          inert={!showActions}
          className={cn(
            "flex items-center justify-end gap-4 transition-opacity duration-500 motion-reduce:transition-none",
            showActions ? "opacity-100" : "opacity-0",
          )}
        >
          <span className="text-sm">
            <span className="text-muted-foreground opacity-60">{t("confidenceLabel")}: </span>
            <span className={cn("font-bold capitalize", CONFIDENCE_COLOR[confidence] ?? "text-muted-foreground")}>
                {t(`confidence.${confidence}` as never)}
            </span>
          </span>
          <Button asChild>
            <Link href={reportHref}>{t("openReport")}</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}