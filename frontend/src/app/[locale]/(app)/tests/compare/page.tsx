"use client";

import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { ScoreBadge } from "@/components/layout/score-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Link, useRouter } from "@/i18n/navigation";
import { formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import { useCompare, useTests } from "@/lib/queries";

interface MetricRow {
  metric: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  note?: string | null;
}

function fmt(metric: string, v: number | null, locale: string): string {
  if (v === null || v === undefined) return "—";
  if (metric.startsWith("count:") || metric.startsWith("goal:") || metric === "score")
    return formatNumber(v, locale, metric === "score" ? 0 : 0);
  return formatPercent(v, 2, locale);
}

function CompareInner() {
  const t = useTranslations("compare");
  const locale = useLocale();
  const params = useSearchParams();
  const router = useRouter();
  const a = params.get("a");
  const b = params.get("b");
  // the same test in both slots can't be compared — never send that request
  const same = !!a && !!b && a === b;
  const completed = useTests(null, "completed", 50);
  const cmp = useCompare(same ? null : a, same ? null : b);

  const options = useMemo(() => completed.data?.items ?? [], [completed.data]);
  const setParam = (key: "a" | "b", value: string) => {
    const q = new URLSearchParams(params.toString());
    q.set(key, value);
    router.replace(`/tests/compare?${q.toString()}`);
  };

  const metricLabel = (m: string) => {
    if (m.startsWith("count:")) return t("counts", { name: titleCase(m.slice(6)) });
    if (m.startsWith("goal:")) return t("goal", { name: titleCase(m.slice(5)) });
    return t.has(`metrics.${m}`) ? t(`metrics.${m}` as never) : titleCase(m);
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")} />
      <div className="grid gap-4 sm:grid-cols-2">
        {(["a", "b"] as const).map((k) => {
          const other = k === "a" ? b : a; // the test picked in the other selector
          return (
            <div key={k} className="space-y-1.5">
              <label htmlFor={`sel-${k}`} className="text-sm font-medium">
                {t(k === "a" ? "versionA" : "versionB")}
              </label>
              <Select value={(k === "a" ? a : b) ?? ""} onValueChange={(v) => setParam(k, v)}>
                <SelectTrigger id={`sel-${k}`}>
                  <SelectValue placeholder={t("pick")} />
                </SelectTrigger>
                <SelectContent>
                  {options.map((o) => (
                    <SelectItem key={o.id} value={o.id} disabled={o.id === other}>
                      {o.title} · {formatDate(o.finished_at ?? o.created_at, locale)} · {o.score ?? "—"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        })}
      </div>
      {!a || !b || same ? (
        <Alert variant="info">
          <AlertDescription>{t("pickBoth")}</AlertDescription>
        </Alert>
      ) : null}
      {cmp.isLoading ? <PageSkeleton rows={3} /> : null}
      {cmp.isError ? <ErrorState error={cmp.error} onRetry={() => cmp.refetch()} /> : null}
      {cmp.data && !same ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {[cmp.data.a, cmp.data.b].map((rep, i) => (
              <Card key={rep.test_id}>
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle>
                    <Link href={`/tests/${rep.test_id}/report`} className="hover:underline">
                      {i === 0 ? "A" : "B"} · {rep.title}
                    </Link>
                  </CardTitle>
                  <ScoreBadge score={rep.score} />
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {titleCase(rep.post_type)} · {titleCase(rep.goal)} · {formatDate(rep.created_at, locale)} ·{" "}
                  {(rep.platforms as { name?: string; code: string }[])
                    .map((p) => p.name ?? titleCase(p.code))
                    .join(", ")}
                </CardContent>
              </Card>
            ))}
          </div>
          {cmp.data.differences.length > 0 ? (
            <Alert variant="warning">
              <AlertDescription>
                <p className="font-medium">{t("differences")}</p>
                <ul className="mt-1 list-disc pl-4">
                  {cmp.data.differences.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("metric")}</TableHead>
                <TableHead className="text-right">A</TableHead>
                <TableHead className="text-right">B</TableHead>
                <TableHead className="text-right">{t("delta")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(cmp.data.metrics as unknown as MetricRow[]).map((row) => (
                <TableRow key={row.metric}>
                  <TableCell className="font-medium">
                    {metricLabel(row.metric)}
                    {row.note ? (
                      <span className="block text-xs text-muted-foreground">{row.note}</span>
                    ) : null}
                  </TableCell>
                  <TableCell className="text-right tabular">{fmt(row.metric, row.a, locale)}</TableCell>
                  <TableCell className="text-right tabular">{fmt(row.metric, row.b, locale)}</TableCell>
                  <TableCell
                    className={`text-right tabular ${row.delta === null ? "" : row.delta > 0 ? "text-success" : row.delta < 0 ? "text-danger" : ""}`}
                  >
                    {row.delta === null
                      ? "—"
                      : `${row.delta > 0 ? "+" : ""}${fmt(row.metric, row.delta, locale)}`}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="text-xs text-muted-foreground">{t("note")}</p>
        </>
      ) : null}
    </div>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <CompareInner />
    </Suspense>
  );
}