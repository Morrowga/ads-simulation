"use client";

import { RefreshCw } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { ScoreBadge } from "@/components/layout/score-badge";
import { StatusBadge } from "@/components/layout/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link } from "@/i18n/navigation";
import { formatDateTime, formatNumber, titleCase } from "@/lib/format";
import { useAdminMutations, useAdminTest } from "@/lib/queries";

type CostRow = {
  stage?: string;
  cost_usd?: number;
  calls?: number;
  tokens_in?: number;
  tokens_out?: number;
  [k: string]: unknown;
};

export default function AdminTestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("admin.testDetail");
  const locale = useLocale();
  const { toast } = useToast();
  const msg = useApiError();
  const test = useAdminTest(id);
  const m = useAdminMutations();
  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  const x = test.data;
  const rerun = async () => {
    try {
      await m.rerun.mutateAsync(id);
      toast({ title: t("rerunQueued"), variant: "success" });
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const costs = x.cost_breakdown as CostRow[];
  return (
    <div className="space-y-6">
      <PageHeader
        title={x.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={x.status} />
            {x.score !== null ? <ScoreBadge score={x.score} /> : null}
            <span>
              {x.user_email} · {titleCase(x.tier_code)} · {x.country_code} · {x.paid_via ?? "—"} ·{" "}
              {t("cancels", { n: x.cancel_count })}
            </span>
          </span>
        }
        actions={
          <>
            <Button variant="outline" asChild>
              <Link href={`/admin/payments?code=`}>{t("payments")}</Link>
            </Button>
            {x.status === "failed" || x.status === "completed" ? (
              <Button onClick={rerun} loading={m.rerun.isPending}>
                <RefreshCw aria-hidden /> {t("rerun")}
              </Button>
            ) : null}
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("stages")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2 text-sm">
              {x.stages.map((s) => (
                <li
                  key={s.stage}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2"
                >
                  <span className="font-medium">{titleCase(s.stage)}</span>
                  <Badge
                    variant={
                      s.status === "done"
                        ? "success"
                        : s.status === "failed"
                          ? "danger"
                          : s.status === "running"
                            ? "info"
                            : "neutral"
                    }
                  >
                    {titleCase(s.status)}
                  </Badge>
                  <span className="ml-auto text-xs tabular text-muted-foreground">
                    {s.started_at ? formatDateTime(s.started_at, locale) : "—"} →{" "}
                    {s.finished_at ? formatDateTime(s.finished_at, locale) : "—"}
                  </span>
                  {s.detail && Object.keys(s.detail).length > 0 ? (
                    <pre className="w-full overflow-x-auto rounded bg-muted p-2 text-[11px]">
                      {JSON.stringify(s.detail, null, 1)}
                    </pre>
                  ) : null}
                </li>
              ))}
              {x.stages.length === 0 ? <li className="text-muted-foreground">{t("noStages")}</li> : null}
            </ol>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("cost")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-2xl font-semibold tabular">${formatNumber(x.cost_usd, locale, 4)}</p>
            <p className="text-sm text-muted-foreground">
              {t("llmCalls", { n: x.llm_calls })} ·{" "}
              {Object.entries(x.tokens)
                .map(([k, v]) => `${titleCase(k)}: ${formatNumber(v, locale)}`)
                .join(" · ")}
            </p>
            {costs.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("stage")}</TableHead>
                    <TableHead className="text-right">{t("calls")}</TableHead>
                    <TableHead className="text-right">{t("usd")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {costs.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell>{titleCase(String(c.stage ?? c.task ?? "—"))}</TableCell>
                      <TableCell className="text-right tabular">
                        {formatNumber(Number(c.calls ?? 0), locale)}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        ${formatNumber(Number(c.cost_usd ?? 0), locale, 4)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </CardContent>
        </Card>
        {x.errors.length > 0 ? (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{t("errors")}</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
                {JSON.stringify(x.errors, null, 2)}
              </pre>
            </CardContent>
          </Card>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>{t("payment")}</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(x.payment ?? {}, null, 2)}
            </pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("versions")}</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded bg-muted p-3 text-xs">
              {JSON.stringify(x.settings_versions, null, 2)}
            </pre>
          </CardContent>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("audit")}</CardTitle>
          </CardHeader>
          <CardContent>
            {x.audit.length === 0 ? <p className="text-sm text-muted-foreground">{t("noAudit")}</p> : null}
            <ul className="space-y-1 text-xs">
              {x.audit.map((a, i) => (
                <li key={i} className="flex flex-wrap gap-2 border-b border-border py-1">
                  <span className="tabular text-muted-foreground">
                    {formatDateTime(String(a.created_at ?? ""), locale)}
                  </span>
                  <span className="font-medium">{String(a.action ?? "")}</span>
                  <span className="text-muted-foreground">{a.actor_email ? String(a.actor_email) : ""}</span>
                  {a.changes ? <span className="font-mono">{JSON.stringify(a.changes)}</span> : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
