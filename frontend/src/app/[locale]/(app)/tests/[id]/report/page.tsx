"use client";

import { Copy, Download, GitCompare } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { ScoreBadge } from "@/components/layout/score-badge";
import { PlatformStatusBadge } from "@/components/layout/status-badge";
import { ReasonContent, ReasonLine } from "@/components/report/evidence-popover";
import { OverviewPanel } from "@/components/report/overview";
import { typedReport } from "@/components/report/report-types";
import { TestTitle } from "@/components/tests/editable-title";
import {
  BetaNote,
  BrandRelationship,
  BuyersBlockers,
  CommentList,
  ComparisonTable,
  FunnelWithReasons,
  metricRows,
  ReactionSplit,
  Section,
  SegmentChart,
  TasteFamiliarity,
  TimingSection,
  TopicBreakdown,
} from "@/components/report/sections";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatNumber, rangeText, scoreBand, titleCase } from "@/lib/format";
import { useReport, useTest, useTestMutations, useTiers } from "@/lib/queries";
import { cn } from "@/lib/utils";

// main tab row: segmented pill control
const MAIN_TABS_LIST =
  "h-auto w-full justify-start gap-1 overflow-x-auto rounded-full bg-muted p-1 sm:w-fit";
const MAIN_TAB_TRIGGER =
  "rounded-full px-4 py-1.5 data-[state=active]:bg-[#0071b5] data-[state=active]:text-white data-[state=active]:shadow-sm";

// sub tab row: outlined pills, filled when active
const SUB_TABS_LIST = "h-auto w-full flex-wrap justify-start gap-2 bg-transparent p-0";
const SUB_TAB_CLASS =
  "rounded-full border border-border bg-background data-[state=active]:border-[#0071b5] data-[state=active]:bg-[#0071b5] data-[state=active]:text-white data-[state=active]:shadow-none";

const SLOT = "\u0001";
function slot(text: string, node: ReactNode): ReactNode {
  const i = text.indexOf(SLOT);
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      {node}
      {text.slice(i + 1)}
    </>
  );
}

// text colour for the score range, from the shared score bands
function scoreTone(score: number | null | undefined): string {
  switch (scoreBand(score)) {
    case "weak":
      return "text-destructive";
    case "below":
    case "average":
      return "text-warning";
    case "good":
    case "strong":
      return "text-success";
    default:
      return "text-muted-foreground";
  }
}

const CONFIDENCE_TONE: Record<string, string> = {
  high: "text-success",
  medium: "text-warning",
  building: "text-destructive",
};

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("report");
  const locale = useLocale();
  const router = useRouter();
  const { toast } = useToast();
  const msg = useApiError();
  const { isAdmin } = useAuth();
  // the test may have completed a moment ago: always take a fresh copy and poll until it is completed
  const test = useTest(id, {
    staleTime: 0,
    refetchInterval: (q) =>
      q.state.data &&
      q.state.data.status !== "completed" &&
      (q.state.data.status === "running" || q.state.data.status === "queued")
        ? 3000
        : false,
  });
  const report = useReport(id, { enabled: !!test.data && test.data.status === "completed" });
  const tiers = useTiers(test.data?.country_code ?? null, 1);
  const m = useTestMutations(id);
  const [combo, setCombo] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");
  const [statsTab, setStatsTab] = useState("funnel");
  const [audTab, setAudTab] = useState("segments");
  const [fbTab, setFbTab] = useState("topics");

  // coming back to this page (browser back / re-open) must not show a stale cached report:
  // force one refetch when the test is completed, and show the skeleton until it has landed
  const testCompleted = test.data?.status === "completed";
  const refetchedOnMount = useRef(false);
  useEffect(() => {
    if (!testCompleted || refetchedOnMount.current) return;
    refetchedOnMount.current = true;
    void report.refetch();
  }, [testCompleted]); // eslint-disable-line react-hooks/exhaustive-deps -- once per mount

  const r = useMemo(() => (report.data ? typedReport(report.data) : null), [report.data]);

  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  if (!test.isFetchedAfterMount) return <PageSkeleton />;
  const td = test.data;
  if (td.status !== "completed") {
    return (
      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("notReady")}</span>
          <Button size="sm" asChild>
            <Link
              href={td.status === "running" || td.status === "queued" ? `/tests/${id}/live` : `/tests/${id}`}
            >
              {t("openTest")}
            </Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
  if (report.isError) return <ErrorState error={report.error} onRetry={() => report.refetch()} />;
  if (!r || !report.isFetchedAfterMount) return <PageSkeleton rows={6} />;

  const comboKeys = Object.keys(r.segments);
  const activeCombo = combo && comboKeys.includes(combo) ? combo : comboKeys[0];
  const [activePlatform, activeAud] = (activeCombo ?? ":0").split(":");
  const activePlatformEntry =
    r.platforms.find((p) => p.code === activePlatform && p.audience_idx === Number(activeAud)) ??
    r.platforms[0];
  const tier = tiers.data?.find((x) => x.code === td.tier_code);
  const runs = r.summary.runs_total;
  const confidence = tier
    ? runs >= tier.runs_target * 0.8
      ? "high"
      : runs >= tier.min_runs
        ? "medium"
        : "building"
    : runs >= 100
      ? "high"
      : "medium";
  const copy = td.ad_copy as { caption?: string };
  const goalRateKey = r.summary.goal_rate_key;
  const counts = r.summary.counts ?? {};
  const keyNumbers = [
    { label: t("key.reach"), value: rangeText(counts.seen, (v) => formatNumber(v, locale)) },
    { label: t("key.clicks"), value: rangeText(counts.clicked, (v) => formatNumber(v, locale)) },
    {
      label: td.goal === "messages" ? t("key.messages") : t("key.purchases"),
      value: rangeText(td.goal === "messages" ? counts.messaged : counts.bought, (v) =>
        formatNumber(v, locale),
      ),
    },
  ];

  const downloadPdf = async () => {
    try {
      const out = await m.reportPdf.mutateAsync(id);
      window.open(out.url, "_blank", "noopener");
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const duplicate = async () => {
    try {
      const c = await m.duplicate.mutateAsync(id);
      router.push(`/tests/new?id=${c.id}&step=1`);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  const labels = {
    score: t("metrics.score"),
    goal: t("metrics.goal", { goal: r.headline.label }),
    reach: t("metrics.reach"),
    stopRate: t("metrics.stopRate"),
    ctr: t("metrics.ctr"),
    goalRate: t("metrics.goalRate"),
  };
  const hasMultiPlatform = new Set(r.platforms.map((p) => p.code)).size > 1;
  const tone = scoreTone(r.raw.score);

  return (
    <div className="space-y-6">
      {/* Summary header */}
      <Card>
        <CardContent className="flex flex-col gap-6 p-6 lg:flex-row lg:items-start">
          <ScoreBadge score={r.raw.score} size="xl" />
          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <h1 className="text-2xl font-semibold">
                <TestTitle testId={id} title={td.title} />
              </h1>
              <p className="text-sm text-muted-foreground">
                {r.summary.score_range
                  ? slot(
                      t("scoreRange", { range: SLOT }),
                      <span className={cn("font-medium", tone)}>
                        {rangeText(r.summary.score_range, (v) => formatNumber(v, locale))}
                      </span>,
                    )
                  : ""}{" "}
                ·{" "}
                {slot(
                  t("confidence", { label: SLOT, runs }),
                  <span className={cn("font-medium", CONFIDENCE_TONE[confidence])}>
                    {t(`confidenceLabels.${confidence}` as never)}
                  </span>,
                )}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {td.profile.preset_name
                  ? t("presetUsed", { name: td.profile.preset_name, version: td.profile.version ?? 1 })
                  : ""}
                {td.profile.mode === "one_time" ? ` · ${t("editedForThisAd")}` : ""} · {titleCase(td.tier_code)}{" "}
                · {formatDateTime(r.raw.created_at, locale)}
              </p>
            </div>
            {r.summary.post_type === "organic" ? (
              <p className="text-sm text-muted-foreground">{t("organicNote")}</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-2 lg:w-48">
            <Button onClick={downloadPdf} loading={m.reportPdf.isPending} disabled={!r.raw.pdf_available}>
              <Download aria-hidden /> {t("downloadPdf")}
            </Button>
            <Button variant="outline" onClick={duplicate} loading={m.duplicate.isPending}>
              <Copy aria-hidden /> {t("duplicateEdit")}
            </Button>
            <Button variant="outline" asChild>
              <Link href={`/tests/compare?a=${id}`}>
                <GitCompare aria-hidden /> {t("compare")}
              </Link>
            </Button>
            {!r.raw.pdf_available ? <p className="text-xs text-muted-foreground">{t("pdfPending")}</p> : null}
          </div>
        </CardContent>
      </Card>

      {/* Showing-for selector (left) + key numbers (right) */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {comboKeys.length > 1 ? (
            <>
              <label htmlFor="combo" className="text-sm text-muted-foreground">
                {t("showingFor")}
              </label>
              <Select value={activeCombo} onValueChange={setCombo}>
                <SelectTrigger id="combo" className="w-72">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {comboKeys.map((k) => {
                    const [pc, a] = k.split(":");
                    const p = r.platforms.find((x) => x.code === pc && x.audience_idx === Number(a));
                    return (
                      <SelectItem key={k} value={k}>
                        {p?.name ?? titleCase(pc)} · {p?.audience_name ?? t("audienceN", { n: Number(a) + 1 })}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </>
          ) : null}
        </div>

        <dl className="ml-auto flex flex-wrap gap-2">
          {keyNumbers.map((k) => (
            <div key={k.label} className="rounded-md border border-[#0071b5] px-3 py-1.5">
              <dt className="text-[11px] leading-tight text-muted-foreground">{k.label}</dt>
              <dd className="text-sm font-medium leading-tight tabular">{k.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="space-y-6">
        <TabsList className={MAIN_TABS_LIST}>
          <TabsTrigger value="overview" className={MAIN_TAB_TRIGGER}>
            {t("tabs.overview")}
          </TabsTrigger>
          <TabsTrigger value="stats" className={MAIN_TAB_TRIGGER}>
            {t("tabs.stats")}
          </TabsTrigger>
          <TabsTrigger value="audience" className={MAIN_TAB_TRIGGER}>
            {t("tabs.audience")}
          </TabsTrigger>
          <TabsTrigger value="feedback" className={MAIN_TAB_TRIGGER}>
            {t("tabs.feedback")}
          </TabsTrigger>
          <TabsTrigger value="timing" className={MAIN_TAB_TRIGGER}>
            {t("sections.timing")}
          </TabsTrigger>
          {hasMultiPlatform ? (
            <TabsTrigger value="platforms" className={MAIN_TAB_TRIGGER}>
              {t("sections.platforms")}
            </TabsTrigger>
          ) : null}
          <TabsTrigger value="details" className={MAIN_TAB_TRIGGER}>
            {t("tabs.details")}
          </TabsTrigger>
        </TabsList>

        {/* ---- Overview: verdict, expected result, what happened, top reasons ---- */}
        <TabsContent value="overview" className="mt-0">
          <OverviewPanel report={r} goal={td.goal} />
        </TabsContent>

        {/* ---- Statistics (sub-tabs): funnel, ad image and caption, buyers ---- */}
        <TabsContent value="stats" className="mt-0">
          <Tabs value={statsTab} onValueChange={setStatsTab} className="space-y-6">
            <TabsList className={SUB_TABS_LIST}>
              <TabsTrigger value="funnel" className={SUB_TAB_CLASS}>
                {t("sections.funnel")}
              </TabsTrigger>
              <TabsTrigger value="reaction" className={SUB_TAB_CLASS}>
                {t("sections.reaction")}
              </TabsTrigger>
              <TabsTrigger value="buyers" className={SUB_TAB_CLASS}>
                {td.goal === "messages" ? t("sections.messagers") : t("sections.buyers")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="funnel" className="mt-0 space-y-6">
              <Section id="funnel" title={t("sections.funnel")} description={t("sections.funnelBody")}>
                <FunnelWithReasons
                  funnel={r.funnel}
                  goal={td.goal}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>

            <TabsContent value="reaction" className="mt-0 space-y-6">
              <Section id="reaction" title={t("sections.reaction")}>
                <ReactionSplit
                  report={r}
                  caption={copy.caption ?? ""}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>

            <TabsContent value="buyers" className="mt-0 space-y-6">
              <Section
                id="buyers"
                title={td.goal === "messages" ? t("sections.messagers") : t("sections.buyers")}
                description={t("sections.buyersBody")}
              >
                <BuyersBlockers
                  platforms={r.platforms}
                  goal={td.goal}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>
          </Tabs>
        </TabsContent>

        {/* ---- Audience (sub-tabs) ---- */}
        <TabsContent value="audience" className="mt-0">
          <Tabs value={audTab} onValueChange={setAudTab} className="space-y-6">
            <TabsList className={SUB_TABS_LIST}>
              {[
                { v: "segments", label: t("sections.segments") },
                { v: "brand", label: t("sections.brand") },
                { v: "taste", label: t("sections.taste") },
                ...(r.audiences.length > 1 ? [{ v: "audiences", label: t("sections.audiences") }] : []),
              ].map((x) => (
                <TabsTrigger key={x.v} value={x.v} className={SUB_TAB_CLASS}>
                  {x.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="segments" className="mt-0 space-y-6">
              <Section id="segments" title={t("sections.segments")} description={t("sections.segmentsBody")}>
                <SegmentChart
                  segments={r.segments[activeCombo ?? ""] ?? {}}
                  goalRateKey={goalRateKey}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>

            <TabsContent value="brand" className="mt-0 space-y-6">
              <Section id="brand" title={t("sections.brand")} description={t("sections.brandBody")}>
                <BrandRelationship
                  table={r.brand[activeCombo ?? ""]}
                  awareness={r.awarenessInputs}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>

            <TabsContent value="taste" className="mt-0 space-y-6">
              <Section id="taste" title={t("sections.taste")}>
                <TasteFamiliarity
                  platform={activePlatformEntry}
                  segments={r.segments[activeCombo ?? ""] ?? {}}
                  reasons={r.raw.reasons}
                  evidence={r.raw.evidence}
                />
              </Section>
            </TabsContent>

            {r.audiences.length > 1 ? (
              <TabsContent value="audiences" className="mt-0 space-y-6">
                <Section id="audiences" title={t("sections.audiences")} description={t("sections.audiencesBody")}>
                  <ComparisonTable
                    columns={r.audiences.map((a) => ({ key: String(a.audience_idx), label: a.name }))}
                    rows={metricRows(
                      r.audiences.map((a) => ({
                        key: String(a.audience_idx),
                        score: a.score,
                        goal_value: a.goal_value,
                        rates: a.rates,
                        counts: a.counts,
                      })),
                      goalRateKey,
                      labels,
                      locale,
                    )}
                  />
                  {r.audiences.map((a) => {
                    const reasons = r.raw.reasons
                      .filter((x) => x.evidence_ids.some((eid) => a.evidence_ids.includes(eid)))
                      .slice(0, 2);
                    return reasons.length ? (
                      <div key={a.audience_idx}>
                        <p className="text-sm font-medium">{a.name}</p>
                        <ul className="space-y-1">
                          {reasons.map((x, i) => (
                            <ReasonLine key={i} reason={x} evidence={r.raw.evidence} />
                          ))}
                        </ul>
                      </div>
                    ) : null;
                  })}
                </Section>
              </TabsContent>
            ) : null}
          </Tabs>
        </TabsContent>

        {/* ---- Feedback (sub-tabs) ---- */}
        <TabsContent value="feedback" className="mt-0">
          <Tabs value={fbTab} onValueChange={setFbTab} className="space-y-6">
            <TabsList className={SUB_TABS_LIST}>
              <TabsTrigger value="topics" className={SUB_TAB_CLASS}>
                {t("sections.topics")}
              </TabsTrigger>
              <TabsTrigger value="comments" className={SUB_TAB_CLASS}>
                {t("sections.comments")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="topics" className="mt-0 space-y-6">
              <Section id="topics" title={t("sections.topics")} description={t("sections.topicsBody")}>
                <TopicBreakdown platforms={r.platforms} reasons={r.raw.reasons} evidence={r.raw.evidence} />
              </Section>
            </TabsContent>

            <TabsContent value="comments" className="mt-0 space-y-6">
              <Section id="comments" title={t("sections.comments")} description={t("sections.commentsBody")}>
                <CommentList comments={r.raw.comments} />
              </Section>
            </TabsContent>
          </Tabs>
        </TabsContent>

        {/* ---- Timing ---- */}
        <TabsContent value="timing" className="mt-0 space-y-6">
          <Section id="timing" title={t("sections.timing")}>
            <TimingSection
              entry={r.timing[activeCombo ?? ""]}
              reasons={r.raw.reasons}
              evidence={r.raw.evidence}
            />
          </Section>
        </TabsContent>

        {/* ---- Platforms (only when more than one platform) ---- */}
        {hasMultiPlatform ? (
          <TabsContent value="platforms" className="mt-0 space-y-6">
            <Section id="platforms" title={t("sections.platforms")} description={t("sections.platformsBody")}>
              <ComparisonTable
                columns={r.platforms
                  .filter((p) => p.audience_idx === 0)
                  .map((p) => ({ key: p.code, label: p.name, badge: <PlatformStatusBadge status={p.status} /> }))}
                rows={metricRows(
                  r.platforms
                    .filter((p) => p.audience_idx === 0)
                    .map((p) => ({
                      key: p.code,
                      score: p.score,
                      goal_value: p.goal_value,
                      rates: p.rates,
                      counts: p.counts,
                    })),
                  goalRateKey,
                  labels,
                  locale,
                )}
              />
              <BetaNote platforms={r.platforms} />
              <ul className="space-y-1">
                {r.raw.reasons
                  .filter((x) => r.raw.evidence.some((e) => x.evidence_ids.includes(e.id) && e.platform))
                  .slice(0, 4)
                  .map((x, i) => (
                    <ReasonLine key={i} reason={x} evidence={r.raw.evidence} />
                  ))}
              </ul>
            </Section>
          </TabsContent>
        ) : null}

        {/* ---- Details ---- */}
        <TabsContent value="details" className="mt-0 space-y-6">
          <Section id="reasons" title={t("sections.allReasons")}>
            <ul className="space-y-2">
              {r.raw.reasons.map((x, i) => (
                <li key={i} className="flex items-baseline gap-3 text-sm">
                  <Badge variant="neutral" className="w-28 shrink-0 justify-center">
                    {titleCase(x.section)}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <ReasonContent reason={x} evidence={r.raw.evidence} />
                  </div>
                </li>
              ))}
            </ul>
          </Section>

          {/* <Section id="method" title={t("sections.method")}>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <dt className="text-muted-foreground">{t("method.runs")}</dt>
              <dd className="tabular">{formatNumber(runs, locale)}</dd>
              <dt className="text-muted-foreground">{t("method.scenarios")}</dt>
              <dd>{r.summary.scenarios.map((s) => s.name ?? s.code).join(", ")}</dd>
              <dt className="text-muted-foreground">{t("method.population")}</dt>
              <dd className="tabular">
                {formatNumber(r.summary.population_per_platform, locale)}{" "}
                {r.summary.scale && r.summary.scale !== 1
                  ? t("method.scale", { scale: formatNumber(r.summary.scale, locale, 1) })
                  : ""}
              </dd>
              <dt className="text-muted-foreground">{t("method.country")}</dt>
              <dd>{td.country_code}</dd>
              <dt className="text-muted-foreground">{t("method.languageGroups")}</dt>
              <dd>
                {r.languageGroups.map((g) => `${g.name} (${formatNumber(g.seen, locale)})`).join(", ") || "—"}
              </dd>
              <dt className="text-muted-foreground">{t("method.engine")}</dt>
              <dd className="font-mono text-xs">{r.raw.engine_version ?? "—"}</dd>
              {isAdmin && r.summary.cost_usd !== undefined ? (
                <>
                  <dt className="text-muted-foreground">{t("method.cost")}</dt>
                  <dd className="tabular">
                    ${r.summary.cost_usd.toFixed(4)} · {r.summary.llm_calls ?? 0} {t("method.llmCalls")}
                  </dd>
                </>
              ) : null}
            </dl>
            <p className="text-sm text-muted-foreground">{r.raw.note}</p>
          </Section> */}
        </TabsContent>
      </Tabs>
    </div>
  );
}