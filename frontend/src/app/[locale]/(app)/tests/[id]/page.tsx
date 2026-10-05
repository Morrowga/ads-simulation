"use client";

import { Copy, Eye, Play, RefreshCw, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { ErrorState } from "@/components/layout/error-state";
import { TestTitle } from "@/components/tests/editable-title";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { ScoreBadge } from "@/components/layout/score-badge";
import { StatusBadge } from "@/components/layout/status-badge";
import { TestSummaryCards } from "@/components/tests/test-summary";
import { StepPreview } from "@/components/wizard/step-preview";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link, useRouter } from "@/i18n/navigation";
import { useTest, useTestMutations } from "@/lib/queries";
import { testHref } from "@/lib/test-routes";

export default function TestOverviewPage() {
  const { id } = useParams<{ id: string }>();
  const t = useTranslations("testOverview");
  const router = useRouter();
  const { toast } = useToast();
  const msg = useApiError();
  const test = useTest(id);
  const m = useTestMutations(id);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  const td = test.data;
  const editable = td.status === "draft" || td.status === "awaiting_payment";
  const ready = td.platforms.length > 0 && td.assets.length > 0 && !!td.profile.profile_id;

  const duplicate = async () => {
    try {
      const copy = await m.duplicate.mutateAsync(td.id);
      toast({ title: t("duplicated"), variant: "success" });
      router.push(`/tests/new?id=${copy.id}&step=1`);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const remove = async () => {
    try {
      await m.remove.mutateAsync(td.id);
      router.push("/dashboard");
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const restart = async () => {
    try {
      await m.restart.mutateAsync(td.id);
      router.push(`/tests/${td.id}/live`);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  const primary = (() => {
    switch (td.status) {
      case "draft":
        return ready ? (
          <Button asChild>
            <Link href={`/tests/${td.id}/confirm`}>
              <Play aria-hidden /> {t("continueConfirm")}
            </Link>
          </Button>
        ) : (
          <Button asChild>
            <Link
              href={`/tests/new?id=${td.id}&step=${!td.profile.profile_id ? 0 : td.assets.length === 0 ? 1 : 3}`}
            >
              {t("continueEditing")}
            </Link>
          </Button>
        );
      case "awaiting_payment":
        return (
          <Button asChild>
            <Link href={`/tests/${td.id}/confirm`}>
              <Play aria-hidden /> {t("continueConfirm")}
            </Link>
          </Button>
        );
      case "payment_review":
        return (
          <Button asChild>
            <Link href={`/tests/${td.id}/checkout`}>{t("paymentStatus")}</Link>
          </Button>
        );
      case "queued":
      case "running":
        return (
          <Button asChild>
            <Link href={`/tests/${td.id}/live`}>
              <Eye aria-hidden /> {t("watchLive")}
            </Link>
          </Button>
        );
      case "completed":
        return (
          <Button asChild>
            <Link href={`/tests/${td.id}/report`}>{t("viewReport")}</Link>
          </Button>
        );
      case "failed":
        return td.rerun_available ? (
          <Button onClick={restart} loading={m.restart.isPending}>
            <RefreshCw aria-hidden /> {t("runAgainFree")}
          </Button>
        ) : (
          <Button asChild>
            <Link href={testHref(td.id, td.status)}>{t("open")}</Link>
          </Button>
        );
      default:
        return null;
    }
  })();

  return (
    <div className="space-y-6">
      <PageHeader
        title={<TestTitle testId={td.id} title={td.title} />}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={td.status} />
            {td.score !== null ? <ScoreBadge score={td.score} /> : null}
            {td.profile.preset_name ? (
              <span>
                {td.profile.preset_name} · v{td.profile.version}
                {td.profile.mode === "one_time" ? ` · ${t("editedForThisAd")}` : ""}
              </span>
            ) : null}
          </span>
        }
        actions={
          <>
            {td.status === "completed" || td.status === "failed" || td.status === "refunded" ? (
              <Button variant="outline" onClick={duplicate} loading={m.duplicate.isPending}>
                <Copy aria-hidden /> {t("duplicateEdit")}
              </Button>
            ) : null}
            {td.status === "draft" ? (
              <Button variant="outline" onClick={() => setConfirmDelete(true)}>
                <Trash2 aria-hidden /> {t("delete")}
              </Button>
            ) : null}
            {primary}
          </>
        }
      />

      {td.status === "draft" && td.free_restart_available && td.cancel_count > 0 ? (
        <Alert variant="success">
          <AlertTitle>{t("freeRestartTitle")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{t("freeRestartBody")}</span>
            <Button size="sm" onClick={restart} loading={m.restart.isPending}>
              <RefreshCw aria-hidden /> {t("restart")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {td.status === "draft" && td.cancel_count > 1 && !td.free_restart_available ? (
        <Alert variant="warning">
          <AlertDescription>{t("secondCancel")}</AlertDescription>
        </Alert>
      ) : null}
      {td.status === "failed" && td.error ? (
        <Alert variant="destructive">
          <AlertTitle>{t("failedTitle")}</AlertTitle>
          <AlertDescription>
            {String((td.error as Record<string, unknown>).message ?? t("failedBody"))}
          </AlertDescription>
        </Alert>
      ) : null}
      {(td.status === "running" || td.status === "queued") && td.progress ? (
        <Alert variant="info">
          <AlertDescription>
            {t("runningNote", { pct: td.progress.pct, label: td.progress.label ?? "" })}
          </AlertDescription>
        </Alert>
      ) : null}

      <TestSummaryCards test={td} editable={editable} />

      {td.platforms.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("feedPreview")}</CardTitle>
          </CardHeader>
          <CardContent>
            <StepPreview test={td} />
          </CardContent>
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={t("deleteTitle")}
        description={t("deleteBody")}
        confirmLabel={t("delete")}
        destructive
        loading={m.remove.isPending}
        onConfirm={remove}
      />
    </div>
  );
}
