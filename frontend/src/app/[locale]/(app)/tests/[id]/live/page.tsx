"use client";

import { AlertTriangle, RefreshCw, Wifi, WifiOff, XCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { ScoreBadge } from "@/components/layout/score-badge";
import { PlatformStatusBadge, StatusBadge } from "@/components/layout/status-badge";
import { ConvergingChart } from "@/components/live/converging-chart";
import { FunnelCounters } from "@/components/live/funnel-counters";
import { LiveComments } from "@/components/live/live-comments";
import { RunFeed } from "@/components/live/run-feed";
import { StageStepper } from "@/components/live/stage-stepper";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { RevealCard } from "@/components/live/reveal-card";
import { isAppError } from "@/lib/errors";
import { formatNumber, rangeText, titleCase, type Range } from "@/lib/format";
import { usePlatforms, useTest, useTestMutations } from "@/lib/queries";
import { useTestProgress, type ComboState } from "@/lib/sse";
import type { AudienceIn } from "@/lib/types";

const CANCEL_STAGES = new Set(["prepare", "analyze_ad", "population", "archetypes", "react"]);

function ComboPanel({ combo, goal }: { combo: ComboState; goal: string }) {
  const t = useTranslations("live");
  const score = combo.estimate?.score ?? null;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <ScoreBadge score={score?.p50 ?? null} size="lg" provisional />
        <div className="text-sm text-muted-foreground">
          <p>{t("runsOf", { done: combo.runs_done, target: combo.runs_target })}</p>
          {score ? <p>{t("scoreRange", { range: rangeText(score, (v) => formatNumber(v)) })}</p> : null}
        </div>
      </div>
      <ConvergingChart points={combo.chart} height={180} />
      <FunnelCounters funnel={combo.funnel} goal={goal} />
    </div>
  );
}

export default function LivePage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("live");
  const { isAdmin } = useAuth();
  const tc = useTranslations("common");
  const router = useRouter();
  const { toast } = useToast();
  const msg = useApiError();
  const test = useTest(id);
  const platforms = usePlatforms();
  const m = useTestMutations(id);
  const mRef = useRef(m);
  mRef.current = m;
  const progress = useTestProgress(
    id,
    !!test.data && test.data.status !== "draft" && test.data.status !== "awaiting_payment",
  );
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reveal, setReveal] = useState(false);

  // completed → 1.5 s reveal, then the report
  useEffect(() => {
    if (!progress.completed) return;
    setReveal(true);
    mRef.current.invalidate();
  }, [progress.completed]);

  // cancelled → back to the draft with the free-restart banner
  useEffect(() => {
    if (progress.cancelled) {
      mRef.current.invalidate();
      router.push(`/tests/${id}`);
    }
  }, [progress.cancelled, id, router]);

  useEffect(() => {
    if (progress.failed) mRef.current.invalidate();
  }, [progress.failed]);

  const cancel = async () => {
    try {
      const out = await m.cancel.mutateAsync(id);
      setCancelOpen(false);
      toast({ title: out.message, variant: "success" });
      if (out.status === "draft") router.push(`/tests/${id}`);
    } catch (e) {
      setCancelOpen(false);
      if (isAppError(e) && e.code === "cancel_window_closed")
        toast({ title: t("cancel.closed"), variant: "destructive" });
      else toast({ title: msg(e), variant: "destructive" });
    }
  };

  const restart = async () => {
    try {
      await m.restart.mutateAsync(id);
      window.location.reload();
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  const combos = useMemo(() => Object.values(progress.combos), [progress.combos]);
  const platformCodes = useMemo(() => Array.from(new Set(combos.map((c) => c.platform))), [combos]);
  const audienceIdxs = useMemo(() => Array.from(new Set(combos.map((c) => c.audience_idx))).sort(), [combos]);
  const audiences = (test.data?.audiences ?? []) as AudienceIn[];

  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  const td = test.data;

  if (td.status === "draft" || td.status === "awaiting_payment" || td.status === "payment_review") {
    return (
      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{td.status === "payment_review" ? t("notStartedReview") : t("notStarted")}</span>
          <Button size="sm" asChild>
            <Link href={td.status === "draft" ? `/tests/${id}` : `/tests/${id}/checkout`}>{tc("open")}</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const status = progress.status ?? td.status;
  const cancelVisible =
    (status === "running" || status === "queued") &&
    progress.cancelWindow &&
    (!progress.stage || CANCEL_STAGES.has(progress.stage));
  const score: Range | null = progress.estimate?.score ?? null;
  const media = td.assets[0];
  const confidence = progress.confidence ?? "building";
  const goal = td.goal;

  if (reveal && progress.completed) {
    const finalScore =
      typeof progress.completed.score === "number"
        ? progress.completed.score
        : (progress.completed.score?.p50 ?? score?.p50 ?? td.score);
    return (
      <RevealCard
        runs={progress.runsDone || progress.runsTarget}
        score={finalScore ?? null}
        confidence={confidence}
        reportHref={`/tests/${id}/report`}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-4">
          <div className="h-16 w-16 shrink-0 overflow-hidden rounded-md bg-zinc-900">
            {media?.url ? (
              media.kind === "video" ? (
                <video
                  src={media.url}
                  className="h-full w-full object-cover"
                  muted
                  playsInline
                  aria-label={t("thumbnail")}
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- asset URL from the API
                <img src={media.url} alt="" className="h-full w-full object-cover" />
              )
            ) : null}
          </div>
          <div>
            <h1 className="text-xl font-semibold">{td.title}</h1>
            <p className="text-sm text-muted-foreground">
              {titleCase(td.tier_code)} ·{" "}
              {td.profile.preset_name ? `${td.profile.preset_name} v${td.profile.version}` : ""} ·{" "}
              {td.platforms.map((p) => p.name ?? titleCase(p.code)).join(", ")}
            </p>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <StatusBadge status={status} />
              {progress.connected ? (
                <span className="flex items-center gap-1">
                  <Wifi className="h-3 w-3" aria-hidden /> {t("connected")}
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <WifiOff className="h-3 w-3" aria-hidden /> {t("reconnecting")}
                </span>
              )}
            </div>
          </div>
        </div>
        {cancelVisible ? (
          <div className="text-right">
            <Button variant="outline" onClick={() => setCancelOpen(true)}>
              {t("cancel.button")}
            </Button>
            <p className="mt-1 text-xs text-muted-foreground">{t("cancel.until")}</p>
          </div>
        ) : null}
      </div>

      <StageStepper stage={progress.stage} status={status} />
      <p className="sr-only" aria-live="polite">
        {progress.label ?? ""}
      </p>

      {progress.failed || status === "failed" ? (
        <Alert variant="destructive">
          <XCircle aria-hidden />
          <AlertTitle>{t("failed.title")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <span>{t("failed.body")}</span>
              {isAdmin ? (
                <p className="font-mono text-xs opacity-70">
                  {progress.failed?.message ||
                    String((td.error as Record<string, unknown> | null)?.message ?? "")}
                </p>
              ) : null}
            </div>
            {(progress.failed?.rerun_available ?? td.rerun_available) ? (
              <Button onClick={restart} loading={m.restart.isPending}>
                <RefreshCw aria-hidden /> {t("failed.runAgain")}
              </Button>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      {status === "queued" ? (
        <Alert variant="info">
          <AlertDescription>{t("queued")}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardContent className="space-y-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium">{progress.label ?? t("preparing")}</span>
            <span className="tabular text-muted-foreground">
              {progress.runsTarget > 0
                ? t("runsOf", { done: progress.runsDone, target: progress.runsTarget })
                : ""}
              {progress.runsTarget > 0
                ? ` · ${t("confidenceLabel")}: ${t(`confidence.${confidence}` as never)}`
                : ""}
            </span>
          </div>
          <Progress value={progress.pct} aria-label={t("progress", { pct: progress.pct })} />
          <p className="text-right text-xs tabular text-muted-foreground">{progress.pct}%</p>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t("scoreTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-3">
            <ScoreBadge score={score?.p50 ?? null} size="xl" provisional />
            <p className="text-sm text-muted-foreground">
              {score
                ? t("scoreRange", { range: rangeText(score, (v) => formatNumber(v)) })
                : t("scoreWaiting")}
            </p>
            {progress.estimate?.goal_value ? (
              <p className="text-sm">
                {t("goalEstimate", {
                  goal: titleCase(goal),
                  range: rangeText(progress.estimate.goal_value, (v) => formatNumber(v)),
                })}
              </p>
            ) : null}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("chart.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ConvergingChart points={progress.chart} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("funnel.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <FunnelCounters funnel={progress.funnel} goal={goal} />
        </CardContent>
      </Card>

      {platformCodes.length > 1 || audienceIdxs.length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("breakdown")}</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue={platformCodes.length > 1 ? `p:${platformCodes[0]}` : `a:${audienceIdxs[0]}`}>
              <TabsList className="h-auto flex-wrap">
                {platformCodes.length > 1
                  ? platformCodes.map((p) => (
                      <TabsTrigger key={p} value={`p:${p}`}>
                        {platforms.data?.find((x) => x.code === p)?.name ?? titleCase(p)}
                        <PlatformStatusBadge
                          status={platforms.data?.find((x) => x.code === p)?.status ?? "full"}
                        />
                      </TabsTrigger>
                    ))
                  : null}
                {audienceIdxs.length > 1
                  ? audienceIdxs.map((a) => (
                      <TabsTrigger key={a} value={`a:${a}`}>
                        {audiences[a]?.name ?? t("feed.audience", { n: a + 1 })}
                      </TabsTrigger>
                    ))
                  : null}
              </TabsList>
              {platformCodes.map((p) => {
                const combo =
                  combos.find((c) => c.platform === p && c.audience_idx === 0) ??
                  combos.find((c) => c.platform === p);
                return combo ? (
                  <TabsContent key={p} value={`p:${p}`}>
                    <ComboPanel combo={combo} goal={goal} />
                  </TabsContent>
                ) : null;
              })}
              {audienceIdxs.map((a) => {
                const combo = combos.find((c) => c.audience_idx === a);
                return combo ? (
                  <TabsContent key={a} value={`a:${a}`}>
                    <ComboPanel combo={combo} goal={goal} />
                  </TabsContent>
                ) : null;
              })}
            </Tabs>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("feed.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <RunFeed batches={progress.batches} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("comments.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            <LiveComments comments={progress.comments} />
          </CardContent>
        </Card>
      </div>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <AlertTriangle className="h-3 w-3" aria-hidden /> {t("closeTabNote")}
      </p>

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title={t("cancel.title")}
        description={t("cancel.body")}
        confirmLabel={t("cancel.confirm")}
        destructive
        loading={m.cancel.isPending}
        onConfirm={cancel}
      />
    </div>
  );
}
