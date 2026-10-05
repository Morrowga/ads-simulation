"use client";

/** Report sections. Every number is paired with its reasons; copy never tells the owner what to change. */
import { useLocale, useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { TopicChip } from "@/components/live/live-comments";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatNumber, formatPercent, rangeText, titleCase, type Range } from "@/lib/format";
import type { CommentOut, EvidenceOut, ReasonOut } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/utils";
import { ReasonLine } from "./evidence-popover";
import {
  BLOCKER_ORDER,
  BRAND_ORDER,
  FUNNEL_ORDER,
  FUNNEL_REASON_SECTIONS,
  type Funnel,
  type ReportPlatform,
  type SegmentRow,
  type SegmentTable,
  type TypedReport,
} from "./report-types";

const tooltipStyle = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 12,
  color: "var(--foreground)",
};

export function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <Card id={id} className="scroll-mt-20">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

export function ReasonList({
  reasons,
  evidence,
  sections,
  limit = 4,
}: {
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
  sections: string[];
  limit?: number;
}) {
  const list = reasons.filter((r) => sections.includes(r.section)).slice(0, limit);
  if (list.length === 0) return null;
  return (
    <ul className="space-y-1.5">
      {list.map((r, i) => (
        <ReasonLine key={`${r.section}-${i}`} reason={r} evidence={evidence} />
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ funnel
export function FunnelWithReasons({
  funnel,
  goal,
  reasons,
  evidence,
}: {
  funnel: Funnel;
  goal: string;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.funnel");
  const tf = useTranslations("live.funnel");
  const locale = useLocale();
  const steps = [...FUNNEL_ORDER];
  if (goal === "messages") steps.splice(steps.indexOf("bought"), 1, "messaged");
  const max = Math.max(1, funnel.seen);
  return (
    <div className="space-y-3">
      {steps.map((k, i) => {
        const v = Number(funnel[k] ?? 0);
        const people = funnel.estimated_people?.[k];
        // Lead with the real-world estimate — that's what a business owner actually cares about.
        // The raw simulated count is a small caveat underneath, not the headline.
        const displayPeople = people !== undefined ? people : v;
        const isFirst = i === 0;
        const why = reasons.find((r) => (FUNNEL_REASON_SECTIONS[k] ?? []).includes(r.section));
        return (
          <div key={k} className="space-y-1.5 rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-sm font-medium text-muted-foreground">{tf(k as never)}</span>
              <span className="text-xl font-semibold tabular">
                {formatNumber(displayPeople, locale)}
                <span className="ml-1 text-xs font-normal text-muted-foreground">{t("people")}</span>
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.max(1, (v / max) * 100)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {isFirst
                ? t("everyoneReached")
                : funnel.seen > 0
                  ? t("shareOfReach", { pct: formatPercent(v / funnel.seen, 0, locale) })
                  : ""}
              {people !== undefined && people !== v
                ? ` — ${t("basedOn", { n: formatNumber(v, locale) })}`
                : ""}
            </p>
            {why ? (
              <div className="mt-1">
                <ul>
                  <ReasonLine reason={why} evidence={evidence} />
                </ul>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ ad image + caption
export function ReactionSplit({
  report,
  caption,
  reasons,
  evidence,
}: {
  report: TypedReport;
  caption: string;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.reaction");
  const locale = useLocale();
  const img = report.summary.ad_image;
  const cap = report.summary.caption;
  const hidden = caption.length > 125 ? caption.slice(125) : "";
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-3">
        <h3 className="font-medium">{t("imageTitle")}</h3>
        <SplitBar
          a={img?.impressed_share ?? 0}
          b={img?.not_impressed_share ?? 0}
          labelA={t("impressed")}
          labelB={t("notImpressed")}
        />
        {img?.top_first_impressions?.length ? (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t("firstImpressions")}
            </p>
            <ul className="mt-1 space-y-1 text-sm">
              {img.top_first_impressions.map((fi) => (
                <li key={fi.text} className="flex justify-between gap-3">
                  <span>“{fi.text}”</span>
                  <span className="tabular text-muted-foreground">{formatPercent(fi.weight, 0, locale)}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <ReasonList reasons={reasons} evidence={evidence} sections={["attention", "dropoff"]} limit={3} />
      </div>
      <div className="space-y-3">
        <h3 className="font-medium">{t("captionTitle")}</h3>
        <SplitBar
          a={cap?.read_share ?? 0}
          b={cap?.ignored_share ?? 0}
          labelA={t("read")}
          labelB={t("ignored")}
        />
        <p className="text-sm text-muted-foreground">
          {t("language", { language: cap?.language ?? "—" })}
          {cap?.language && cap.language !== "en" && cap.english ? ` · ${t("englishUsed")}` : ""}
        </p>
        {hidden ? (
          <div className="rounded-md border border-warning/40 bg-warning-bg p-3 text-sm">
            <p className="font-medium">{t("hiddenTitle")}</p>
            <p className="mt-1 text-muted-foreground">…{hidden}</p>
          </div>
        ) : null}
        <ReasonList reasons={reasons} evidence={evidence} sections={["language"]} limit={3} />
      </div>
    </div>
  );
}

function SplitBar({ a, b, labelA, labelB }: { a: number; b: number; labelA: string; labelB: string }) {
  const locale = useLocale();
  const total = a + b || 1;
  return (
    <div>
      <div
        className="flex h-4 w-full overflow-hidden rounded-full"
        role="img"
        aria-label={`${labelA} ${formatPercent(a / total, 0, locale)}, ${labelB} ${formatPercent(b / total, 0, locale)}`}
      >
        <div className="bg-success" style={{ width: `${(a / total) * 100}%` }} />
        <div className="bg-neutral/40" style={{ width: `${(b / total) * 100}%` }} />
      </div>
      <div className="mt-1 flex justify-between text-xs">
        <span>
          <span className="font-medium text-success">{formatPercent(a / total, 0, locale)}</span> {labelA}
        </span>
        <span>
          <span className="font-medium">{formatPercent(b / total, 0, locale)}</span> {labelB}
        </span>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ comment topics
export function TopicBreakdown({
  platforms,
  reasons,
  evidence,
}: {
  platforms: ReportPlatform[];
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.topics");
  const tt = useTranslations("topics");
  const locale = useLocale();
  const totals = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const p of platforms)
      for (const [k, v] of Object.entries(p.comment_topics ?? {})) acc[k] = (acc[k] ?? 0) + v.count;
    return acc;
  }, [platforms]);
  const sum = Object.values(totals).reduce((a, x) => a + x, 0) || 1;
  const questions = ((totals.price ?? 0) + (totals.product_detail ?? 0) + (totals.service ?? 0)) / sum;
  const order = ["price", "product_detail", "service", "positive", "negative", "other"];
  return (
    <div className="space-y-3">
      <ul className="grid gap-2 sm:grid-cols-3">
        {order
          .filter((k) => totals[k] !== undefined)
          .map((k) => (
            <li
              key={k}
              className="flex items-center justify-between rounded-md border border-border p-3 text-sm"
            >
              <TopicChip topic={k} />
              <span className="tabular">
                {formatNumber(totals[k], locale, 1)}{" "}
                <span className="text-muted-foreground">({formatPercent(totals[k] / sum, 0, locale)})</span>
              </span>
            </li>
          ))}
      </ul>
      <p className="text-sm">{t("insight", { pct: formatPercent(questions, 0, locale) })}</p>
      <p className="text-xs text-muted-foreground">
        {t("perRun")} · {tt("questionsNote")}
      </p>
      <ReasonList reasons={reasons} evidence={evidence} sections={["comments"]} limit={3} />
    </div>
  );
}

// ------------------------------------------------------------------ comments
export function CommentList({ comments, max = 20 }: { comments: CommentOut[]; max?: number }) {
  const t = useTranslations("report.comments");
  const [topic, setTopic] = useState<string>("all");
  const topics = useMemo(
    () => Array.from(new Set(comments.map((c) => c.topic).filter((x): x is string => !!x))),
    [comments],
  );
  const shown = comments.filter((c) => topic === "all" || c.topic === topic).slice(0, max);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("filter")}>
        <Button size="sm" variant={topic === "all" ? "default" : "outline"} onClick={() => setTopic("all")}>
          {t("all")}
        </Button>
        {topics.map((tp) => (
          <Button
            key={tp}
            size="sm"
            variant={topic === tp ? "default" : "outline"}
            onClick={() => setTopic(tp)}
          >
            {titleCase(tp)}
          </Button>
        ))}
      </div>
      {shown.length === 0 ? <p className="text-sm text-muted-foreground">{t("none")}</p> : null}
      <ul className="space-y-2">
        {shown.map((c, i) => (
          <li key={i} className="rounded-md border border-border p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{c.archetype}</span>
              {!/speaking/i.test(c.archetype) ? (
                <span>· {t("speaking", { group: c.language_group })}</span>
              ) : null}
              <span>· {titleCase(c.platform)}</span>
              {c.scenario ? <span>· {titleCase(c.scenario)}</span> : null}
              <span className="ml-auto">
                <TopicChip topic={c.topic} />
              </span>
            </div>
            <p className="mt-1">{c.text}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ------------------------------------------------------------------ segments
function segmentRows(table: SegmentTable | undefined, rateKey: string) {
  if (!table) return [];
  return Object.entries(table)
    .filter(([, row]) => (row.seen ?? 0) > 0)
    .map(([label, row]) => ({
      label: titleCase(label),
      seen: row.seen,
      rate: Number(row[rateKey] ?? 0),
      clicked: Number(row.clicked ?? 0),
      stopped: Number(row.stopped ?? 0),
    }));
}

export function SegmentChart({
  segments,
  goalRateKey,
  reasons,
  evidence,
}: {
  segments: Record<string, SegmentTable>;
  goalRateKey: string;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.segments");
  const locale = useLocale();
  const dims = [
    "age_band",
    "gender",
    "familiarity",
    "patience",
    "skeptical",
    "reads_caption",
    "follower",
    "language_group",
  ].filter((d) => segments[d]);
  const [dim, setDim] = useState(dims[0] ?? "age_band");
  const rateKey =
    goalRateKey === "buy_rate"
      ? "bought_rate"
      : goalRateKey === "message_rate"
        ? "messaged_rate"
        : goalRateKey === "engagement_rate"
          ? "engaged_rate"
          : goalRateKey === "stop_rate"
            ? "stopped_rate"
            : "clicked_rate";
  const rows = segmentRows(segments[dim], rateKey);
  const sorted = [...rows].sort((a, b) => b.rate - a.rate);
  const animate = !prefersReducedMotion();
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("dimension")}>
        {dims.map((d) => (
          <Button key={d} size="sm" variant={dim === d ? "default" : "outline"} onClick={() => setDim(d)}>
            {t.has(`dims.${d}`) ? t(`dims.${d}` as never) : titleCase(d)}
          </Button>
        ))}
      </div>
      {rows.length > 0 ? (
        <div style={{ height: 220 }} role="img" aria-label={t("chartAria", { dimension: titleCase(dim) })}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                tickLine={false}
                interval={0}
              />
              <YAxis
                tickFormatter={(v: number) => formatPercent(v, 1, locale)}
                tick={{ fontSize: 11 }}
                stroke="var(--muted-foreground)"
                tickLine={false}
                width={48}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(v, _n, item) => [
                  `${formatPercent(typeof v === "number" ? v : Number(v ?? 0), 2, locale)} · ${formatNumber((item as { payload?: { seen: number } }).payload?.seen ?? 0, locale)} ${t("seen")}`,
                  titleCase(rateKey),
                ]}
              />
              <Bar dataKey="rate" fill="var(--chart-1)" radius={[4, 4, 0, 0]} isAnimationActive={animate} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("noData")}</p>
      )}
      {sorted.length >= 2 ? (
        <div className="grid gap-2 sm:grid-cols-2 text-sm">
          <div className="rounded-md border border-success/40 bg-success-bg p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("strongest")}</p>
            <p className="font-medium">
              {sorted[0].label} · {formatPercent(sorted[0].rate, 2, locale)}
            </p>
          </div>
          <div className="rounded-md border border-danger/40 bg-danger-bg p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("weakest")}</p>
            <p className="font-medium">
              {sorted[sorted.length - 1].label} · {formatPercent(sorted[sorted.length - 1].rate, 2, locale)}
            </p>
          </div>
        </div>
      ) : null}
      <ReasonList reasons={reasons} evidence={evidence} sections={["segments", "language"]} limit={4} />
    </div>
  );
}

// ------------------------------------------------------------------ brand relationship
export function BrandRelationship({
  table,
  awareness,
  reasons,
  evidence,
}: {
  table: SegmentTable | undefined;
  awareness: Record<string, unknown>;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.brand");
  const locale = useLocale();
  const rows: { key: string; row: SegmentRow }[] = BRAND_ORDER.filter((k) => table?.[k]).map((k) => ({
    key: k,
    row: table![k],
  }));
  const total = rows.reduce((a, r) => a + (r.row.seen ?? 0), 0) || 1;
  const followers = Number(awareness.followers ?? 0);
  const months = Number(awareness.months_in_business ?? 0);
  const isNew = followers < 500 || months < 6;
  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("group")}</TableHead>
            <TableHead className="text-right">{t("reach")}</TableHead>
            <TableHead className="text-right">{t("share")}</TableHead>
            <TableHead className="text-right">{t("stopRate")}</TableHead>
            <TableHead className="text-right">{t("clickRate")}</TableHead>
            <TableHead className="text-right">{t("buyRate")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(({ key, row }) => (
            <TableRow key={key}>
              <TableCell className="font-medium">{t(`groups.${key}` as never)}</TableCell>
              <TableCell className="text-right tabular">{formatNumber(row.seen, locale)}</TableCell>
              <TableCell className="text-right tabular">
                {formatPercent(row.seen / total, 0, locale)}
              </TableCell>
              <TableCell className="text-right tabular">
                {formatPercent(Number(row.stopped_rate ?? 0), 1, locale)}
              </TableCell>
              <TableCell className="text-right tabular">
                {formatPercent(Number(row.clicked_rate ?? 0), 2, locale)}
              </TableCell>
              <TableCell className="text-right tabular">
                {formatPercent(Number(row.bought_rate ?? 0), 2, locale)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {isNew ? (
        <p className="text-sm text-muted-foreground">
          {t("newBrandNote", { followers: formatNumber(followers, locale), months })}
        </p>
      ) : null}
      <ReasonList reasons={reasons} evidence={evidence} sections={["brand"]} limit={3} />
    </div>
  );
}

// ------------------------------------------------------------------ taste & familiarity
export function TasteFamiliarity({
  platform,
  segments,
  reasons,
  evidence,
}: {
  platform: ReportPlatform | undefined;
  segments: Record<string, SegmentTable>;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.taste");
  const locale = useLocale();
  const taste = platform?.taste;
  const fam = segments.familiarity;
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <h3 className="font-medium">{t("tasteTitle")}</h3>
        {taste && taste.mismatch_share_of_seen !== undefined ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">{t("mismatchShare")}</dt>
            <dd className="tabular text-right">{formatPercent(taste.mismatch_share_of_seen, 0, locale)}</dd>
            <dt className="text-muted-foreground">{t("matchStop")}</dt>
            <dd className="tabular text-right">{formatPercent(taste.match_stop_rate ?? 0, 1, locale)}</dd>
            <dt className="text-muted-foreground">{t("mismatchStop")}</dt>
            <dd className="tabular text-right">{formatPercent(taste.mismatch_stop_rate ?? 0, 1, locale)}</dd>
            <dt className="text-muted-foreground">{t("mismatchNegative")}</dt>
            <dd className="tabular text-right">
              {formatPercent(taste.mismatch_negative_share ?? 0, 0, locale)}
            </dd>
            {taste.dimensions?.length ? (
              <>
                <dt className="text-muted-foreground">{t("dimensions")}</dt>
                <dd className="text-right">{taste.dimensions.map(titleCase).join(", ")}</dd>
              </>
            ) : null}
          </dl>
        ) : (
          <p className="text-sm text-muted-foreground">{t("noTaste")}</p>
        )}
        <ReasonList reasons={reasons} evidence={evidence} sections={["taste"]} limit={3} />
      </div>
      <div className="space-y-2">
        <h3 className="font-medium">{t("familiarityTitle")}</h3>
        {fam ? (
          <ul className="space-y-1 text-sm">
            {Object.entries(fam)
              .filter(([, r]) => r.seen > 0)
              .map(([k, r]) => (
                <li key={k} className="flex justify-between gap-3">
                  <span>{t.has(`familiarity.${k}`) ? t(`familiarity.${k}` as never) : titleCase(k)}</span>
                  <span className="tabular text-muted-foreground">
                    {formatNumber(r.seen, locale)} {t("seen")} ·{" "}
                    {formatPercent(Number(r.stopped_rate ?? 0), 1, locale)} {t("stopped")} ·{" "}
                    {formatPercent(Number(r.clicked_rate ?? 0), 2, locale)} {t("clicked")}
                  </span>
                </li>
              ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("noFamiliarity")}</p>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ timing
export function TimingSection({
  entry,
  reasons,
  evidence,
}: {
  entry:
    | {
        timing: import("./report-types").Timing;
        fatigue: import("./report-types").Fatigue;
        dropoff: import("./report-types").Dropoff;
      }
    | undefined;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.timing");
  const locale = useLocale();
  const animate = !prefersReducedMotion();
  if (!entry) return <p className="text-sm text-muted-foreground">{t("noData")}</p>;
  const hours = (entry.timing.hour_of_day_stops ?? []).map((v, h) => ({ hour: `${h}:00`, stops: v }));
  const days = (entry.timing.daily_reach ?? []).map((v, d) => ({ day: t("dayN", { n: d + 1 }), reach: v }));
  const fatigue = (entry.fatigue.stop_rate_by_exposure ?? []).map((v, i) => ({
    view: t("viewN", { n: i + 1 }),
    rate: v,
    seen: entry.fatigue.seen_by_exposure?.[i] ?? 0,
  }));
  const fatiguePoint = fatigue.findIndex((f, i) => i > 0 && f.rate < (fatigue[0]?.rate ?? 0) * 0.6);
  const bestHour = hours.length ? hours.reduce((b, h) => (h.stops > b.stops ? h : b), hours[0]) : null;
  return (
    <div className="space-y-4">
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium">{t("hourTitle")}</h3>
          {hours.length ? (
            <div
              style={{ height: 160 }}
              role="img"
              aria-label={t("hourAria", { hour: bestHour?.hour ?? "—" })}
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hours} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <XAxis
                    dataKey="hour"
                    tick={{ fontSize: 10 }}
                    interval={3}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v) => [
                      formatNumber(typeof v === "number" ? v : Number(v ?? 0), locale, 1),
                      t("stops"),
                    ]}
                  />
                  <Bar dataKey="stops" fill="var(--chart-1)" isAnimationActive={animate} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}
          {bestHour ? <p className="mt-1 text-sm">{t("bestHour", { hour: bestHour.hour })}</p> : null}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium">{t("dayTitle")}</h3>
          {days.length ? (
            <div style={{ height: 160 }} role="img" aria-label={t("dayAria")}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={days} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(v) => [
                      formatNumber(typeof v === "number" ? v : Number(v ?? 0), locale),
                      t("reach"),
                    ]}
                  />
                  <Bar dataKey="reach" fill="var(--chart-2)" isAnimationActive={animate} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : null}
          {entry.timing.first_24h_reach_share !== undefined ? (
            <p className="mt-1 text-sm">
              {t("first24h", { pct: formatPercent(entry.timing.first_24h_reach_share, 0, locale) })}
            </p>
          ) : null}
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">{t("fatigueTitle")}</h3>
        <ul className="flex flex-wrap gap-2 text-sm">
          {fatigue.slice(0, 6).map((f, i) => (
            <li
              key={f.view}
              className={`rounded-md border p-2 ${i === fatiguePoint ? "border-warning bg-warning-bg" : "border-border"}`}
            >
              <p className="text-xs text-muted-foreground">{f.view}</p>
              <p className="tabular font-medium">{formatPercent(f.rate, 1, locale)}</p>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-sm">
          {fatiguePoint > 0 ? t("fatiguePoint", { n: fatiguePoint + 1 }) : t("noFatigue")} ·{" "}
          {t("frequency", { n: formatNumber(entry.fatigue.mean_frequency, locale, 2) })}
        </p>
        {entry.dropoff?.avg_watch_s ? (
          <p className="text-sm text-muted-foreground">
            {t("watch", { s: formatNumber(entry.dropoff.avg_watch_s, locale, 1) })}
            {entry.dropoff.offer_visible_at_s !== null && entry.dropoff.offer_visible_at_s !== undefined
              ? ` · ${t("offerAt", { s: entry.dropoff.offer_visible_at_s, pct: formatPercent(entry.dropoff.all_left_before_offer_share, 0, locale) })}`
              : ""}
          </p>
        ) : null}
      </div>
      <ReasonList reasons={reasons} evidence={evidence} sections={["timing", "dropoff"]} limit={3} />
    </div>
  );
}

// ------------------------------------------------------------------ buyers vs non-buyers
export function BuyersBlockers({
  platforms,
  goal,
  reasons,
  evidence,
}: {
  platforms: ReportPlatform[];
  goal: string;
  reasons: ReasonOut[];
  evidence: EvidenceOut[];
}) {
  const t = useTranslations("report.blockers");
  const locale = useLocale();
  const totals: Record<string, number> = {};
  for (const p of platforms)
    for (const [k, v] of Object.entries(p.blockers ?? {})) totals[k] = (totals[k] ?? 0) + v.count;
  const sum = Object.values(totals).reduce((a, x) => a + x, 0) || 1;
  const first = platforms[0];
  const clicked = first?.funnel.clicked ?? 0;
  const converted = goal === "messages" ? (first?.funnel.messaged ?? 0) : (first?.funnel.bought ?? 0);
  return (
    <div className="space-y-3">
      <p className="text-sm">
        {t("summary", {
          clicked: formatNumber(clicked, locale),
          converted: formatNumber(converted, locale),
          pct: clicked ? formatPercent(converted / clicked, 1, locale) : "—",
        })}
      </p>
      <ul className="space-y-2">
        {BLOCKER_ORDER.filter((k) => totals[k] !== undefined).map((k) => (
          <li key={k}>
            <div className="mb-1 flex justify-between text-sm">
              <span>{t(`kinds.${k}` as never)}</span>
              <span className="tabular text-muted-foreground">
                {formatPercent(totals[k] / sum, 0, locale)}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
              <div
                className="h-full rounded-full bg-chart-5"
                style={{ width: `${(totals[k] / sum) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      <ReasonList reasons={reasons} evidence={evidence} sections={["blockers"]} limit={3} />
    </div>
  );
}

// ------------------------------------------------------------------ comparisons
export function ComparisonTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string; badge?: React.ReactNode }[];
  rows: { label: string; values: Record<string, string> }[];
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead />
          {columns.map((c) => (
            <TableHead key={c.key} className="text-right">
              <span className="inline-flex items-center gap-1">
                {c.label} {c.badge}
              </span>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.label}>
            <TableCell className="font-medium">{r.label}</TableCell>
            {columns.map((c) => (
              <TableCell key={c.key} className="text-right tabular">
                {r.values[c.key] ?? "—"}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function metricRows(
  entries: {
    key: string;
    score: Range | null;
    goal_value: Range | null;
    rates: Record<string, Range> | null;
    counts: Record<string, Range> | null;
  }[],
  goalRateKey: string,
  labels: Record<string, string>,
  locale: string,
) {
  const pct = (r: Range | null | undefined) => (r ? rangeText(r, (v) => formatPercent(v, 2, locale)) : "—");
  const num = (r: Range | null | undefined) => (r ? rangeText(r, (v) => formatNumber(v, locale)) : "—");
  return [
    {
      label: labels.score,
      values: Object.fromEntries(
        entries.map((e) => [e.key, e.score ? String(Math.round(e.score.p50 ?? 0)) : "—"]),
      ),
    },
    { label: labels.goal, values: Object.fromEntries(entries.map((e) => [e.key, num(e.goal_value)])) },
    { label: labels.reach, values: Object.fromEntries(entries.map((e) => [e.key, num(e.counts?.seen)])) },
    {
      label: labels.stopRate,
      values: Object.fromEntries(entries.map((e) => [e.key, pct(e.rates?.stop_rate)])),
    },
    { label: labels.ctr, values: Object.fromEntries(entries.map((e) => [e.key, pct(e.rates?.ctr)])) },
    {
      label: labels.goalRate,
      values: Object.fromEntries(entries.map((e) => [e.key, pct(e.rates?.[goalRateKey])])),
    },
  ];
}

export function BetaNote({ platforms }: { platforms: ReportPlatform[] }) {
  const t = useTranslations("report.platforms");
  const beta = platforms.filter((p) => p.status === "beta");
  if (beta.length === 0) return null;
  return (
    <p className="flex items-center gap-2 text-xs text-muted-foreground">
      <Badge variant="warning">{t("beta")}</Badge>{" "}
      {t("betaNote", { names: Array.from(new Set(beta.map((p) => p.name))).join(", ") })}
    </p>
  );
}
