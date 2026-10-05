"use client";

/** Sandbox preview: run a sample test with draft settings and compare with the published version. */
import { FlaskConical } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatNumber, formatPercent, titleCase } from "@/lib/format";
import { useAdminMutations } from "@/lib/queries";
import type { SandboxResultOut, SandboxRunIn } from "@/lib/types";

interface CompRow {
  metric: string;
  published: number | null;
  draft: number | null;
  delta: number | null;
  relative: number | null;
}

export function SandboxDialog({ params, label }: { params: Partial<SandboxRunIn>; label?: string }) {
  const t = useTranslations("admin.sandbox");
  const locale = useLocale();
  const m = useAdminMutations();
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState(20);
  const [agents, setAgents] = useState(3000);
  const [realLlm, setRealLlm] = useState(false);
  const [result, setResult] = useState<SandboxResultOut | null>(null);
  const [error, setError] = useState<unknown>(null);

  const run = async () => {
    setError(null);
    try {
      setResult(
        await m.sandbox.mutateAsync({ ...params, use_drafts: true, use_real_llm: realLlm, runs, agents }),
      );
    } catch (e) {
      setError(e);
    }
  };

  const fmt = (metric: string, v: number | null) =>
    v === null || v === undefined
      ? "—"
      : /rate|share|ctr|cvr/.test(metric) && Math.abs(v) <= 1
        ? formatPercent(v, 2, locale)
        : formatNumber(v, locale, 2);

  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        <FlaskConical aria-hidden /> {label ?? t("button")}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t("title")}</DialogTitle>
            <DialogDescription>{t("body")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField id="sb-runs" label={t("runs")}>
              <Input
                id="sb-runs"
                type="number"
                min={4}
                max={150}
                value={runs}
                onChange={(e) => setRuns(Number(e.target.value))}
              />
            </FormField>
            <FormField id="sb-agents" label={t("agents")}>
              <Input
                id="sb-agents"
                type="number"
                min={500}
                max={50000}
                step={500}
                value={agents}
                onChange={(e) => setAgents(Number(e.target.value))}
              />
            </FormField>
            <label className="flex items-center gap-2 self-end pb-2 text-sm">
              <Checkbox checked={realLlm} onCheckedChange={(c) => setRealLlm(c === true)} /> {t("realLlm")}
            </label>
          </div>
          <InlineError error={error} />
          {result ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                {t("meta", { ms: result.elapsed_ms, provider: result.llm_provider })}
                {result.note ? ` · ${result.note}` : ""}
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("metric")}</TableHead>
                    <TableHead className="text-right">{t("published")}</TableHead>
                    <TableHead className="text-right">{t("draft")}</TableHead>
                    <TableHead className="text-right">{t("delta")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(result.comparison as unknown as CompRow[]).map((row) => (
                    <TableRow key={row.metric}>
                      <TableCell className="font-medium">{titleCase(row.metric)}</TableCell>
                      <TableCell className="text-right tabular">{fmt(row.metric, row.published)}</TableCell>
                      <TableCell className="text-right tabular">{fmt(row.metric, row.draft)}</TableCell>
                      <TableCell
                        className={`text-right tabular ${row.delta === null ? "" : row.delta > 0 ? "text-success" : row.delta < 0 ? "text-danger" : ""}`}
                      >
                        {row.delta === null
                          ? "—"
                          : `${row.delta > 0 ? "+" : ""}${fmt(row.metric, row.delta)}`}
                        {row.relative !== null && row.relative !== undefined ? (
                          <span className="text-muted-foreground">
                            {" "}
                            ({formatPercent(row.relative, 0, locale)})
                          </span>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <p className="text-xs text-muted-foreground">
                {t("versions")}: {JSON.stringify(result.draft_versions)} →{" "}
                {JSON.stringify(result.published_versions)}
              </p>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              {t("close")}
            </Button>
            <Button onClick={run} loading={m.sandbox.isPending}>
              {t("run")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
