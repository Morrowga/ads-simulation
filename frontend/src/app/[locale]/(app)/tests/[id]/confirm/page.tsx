"use client";

import { AlertTriangle, ArrowRight, CheckCircle2, Info, RefreshCw, XCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { TestSummaryCards } from "@/components/tests/test-summary";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Link, useRouter } from "@/i18n/navigation";
import { isAppError } from "@/lib/errors";
import { formatDate, titleCase } from "@/lib/format";
import { useTest, useTestMutations } from "@/lib/queries";
import type { ConfirmOut } from "@/lib/types";

export default function ConfirmPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("confirm");
  const locale = useLocale();
  const router = useRouter();
  const test = useTest(id);
  const m = useTestMutations(id);
  const [result, setResult] = useState<ConfirmOut | null>(null);
  const [blocking, setBlocking] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [checked, setChecked] = useState(false);
  const ran = useRef(false);

  const run = async () => {
    setError(null);
    setBlocking([]);
    try {
      const out = await m.confirm.mutateAsync(id);
      setResult(out);
    } catch (e) {
      if (isAppError(e) && e.errorList.length > 0) setBlocking(e.errorList);
      else setError(e);
    }
  };

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    void run();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- confirm once on mount

  if (test.isLoading || (!result && m.confirm.isPending && blocking.length === 0 && !error))
    return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  const td = test.data;

  if (td.status !== "draft" && td.status !== "awaiting_payment") {
    return (
      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("notConfirmable")}</span>
          <Button size="sm" variant="outline" asChild>
            <Link href={`/tests/${td.id}`}>{t("openTest")}</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const dup = result?.duplicate;
  const isDuplicate = !!dup?.is_duplicate;
  const canContinue = !!result && !isDuplicate && checked;

  return (
    // -my-6 cancels the app shell's own `py-6` on <main> so this page can own the full viewport
    // height below the navbar; pt-6/pb-6 below restore that same visual spacing. Only the middle
    // summary/checks column scrolls — the header and the final checkbox+continue card stay put,
    // so the continue action is always visible without scrolling down to find it.
    <div className="-my-6 flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="shrink-0 pt-6">
        <PageHeader
          title={t("title")}
          description={t("description")}
          actions={
            <Button variant="outline" onClick={run} loading={m.confirm.isPending}>
              <RefreshCw aria-hidden /> {t("recheck")}
            </Button>
          }
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-6 py-6">
          {blocking.length > 0 ? (
            <Alert variant="destructive">
              <XCircle aria-hidden />
              <AlertTitle>{t("blockingTitle")}</AlertTitle>
              <AlertDescription>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {blocking.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
                <Button asChild size="sm" variant="outline" className="mt-3">
                  <Link
                    href={`/tests/new?id=${td.id}&step=${td.assets.length === 0 ? 1 : td.platforms.length === 0 ? 3 : 0}`}
                  >
                    {t("fixInputs")}
                  </Link>
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}
          {error ? <ErrorState error={error} onRetry={run} /> : null}

          <TestSummaryCards
            test={td}
            editable
            priceUsdMinor={result?.price.total_usd_minor}
            priceLocal={result?.price.local ?? null}
          />

          {result ? (
            <>
              {result.spec_checks.length > 0 ? (
                <Card>
                  <CardHeader>
                    <CardTitle>{t("specChecks")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm">
                      {result.spec_checks.map((s, i) => (
                        <li key={i} className="flex items-start gap-2">
                          {s.ok ? (
                            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
                          ) : (
                            <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                          )}
                          <span>
                            <span className="font-medium">
                              {titleCase(s.platform)}
                              {s.placement ? ` · ${titleCase(s.placement)}` : ""}:
                            </span>{" "}
                            {s.message}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ) : null}

              {result.warnings.map((w, i) => (
                <Alert key={i} variant="warning">
                  <AlertTriangle aria-hidden />
                  <AlertDescription>{w}</AlertDescription>
                </Alert>
              ))}

              {!isDuplicate && result.changed_fields.length > 0 && dup?.completed_at ? (
                <Alert variant="info">
                  <Info aria-hidden />
                  <AlertDescription>
                    {t("closeMatch", {
                      date: formatDate(dup.completed_at, locale),
                      fields: result.changed_fields
                        .map((f) => (t.has(`fields.${f}`) ? t(`fields.${f}` as never) : titleCase(f)))
                        .join(", "),
                    })}
                  </AlertDescription>
                </Alert>
              ) : null}

              {result.engine_updated ? (
                <Alert variant="info">
                  <Info aria-hidden />
                  <AlertDescription>{t("engineUpdated")}</AlertDescription>
                </Alert>
              ) : null}

              {isDuplicate && dup ? (
                <Alert variant="destructive">
                  <XCircle aria-hidden />
                  <AlertTitle>{t("duplicateTitle")}</AlertTitle>
                  <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <span>
                      {t("duplicateBody", {
                        date: formatDate(dup.completed_at, locale),
                        score: dup.score ?? "—",
                      })}
                    </span>
                    {dup.test_id ? (
                      <Button size="sm" variant="outline" asChild>
                        <Link href={`/tests/${dup.test_id}/report`}>{t("viewResult")}</Link>
                      </Button>
                    ) : null}
                  </AlertDescription>
                </Alert>
              ) : null}
            </>
          ) : null}
        </div>
      </div>

      {result && !isDuplicate ? (
        <div className="shrink-0 pb-6 pt-4">
          <Card>
            <CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <label className="flex items-start gap-3 text-sm">
                <Checkbox
                  checked={checked}
                  onCheckedChange={(v) => setChecked(v === true)}
                  id="checked"
                  className="mt-0.5"
                />
                <span>{t("iChecked")}</span>
              </label>
              <Button onClick={() => router.push(`/tests/${td.id}/checkout`)} disabled={!canContinue}>
                {t("continueCheckout")} <ArrowRight aria-hidden />
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}