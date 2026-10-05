"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { SandboxDialog } from "@/components/admin/sandbox-dialog";
import { VersionHistory, VersionStatusBadge } from "@/components/admin/version-history";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toaster";
import { titleCase } from "@/lib/format";
import { useAdminMutations, useAdminWeights } from "@/lib/queries";
import type { VersionLike } from "@/components/admin/version-history";

type NumMap = Record<string, number>;

function NumberGrid({ id, values, onChange }: { id: string; values: NumMap; onChange: (v: NumMap) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Object.entries(values).map(([k, v]) => (
        <FormField key={k} id={`${id}-${k}`} label={titleCase(k)}>
          <Input
            id={`${id}-${k}`}
            type="number"
            step="0.01"
            value={v}
            onChange={(e) => onChange({ ...values, [k]: Number(e.target.value) })}
          />
        </FormField>
      ))}
    </div>
  );
}

export default function AdminWeightsPage() {
  const t = useTranslations("admin.weights");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();
  const weights = useAdminWeights();
  const m = useAdminMutations();
  const [behavior, setBehavior] = useState<NumMap>({});
  const [scoreByGoal, setScoreByGoal] = useState<Record<string, NumMap>>({});
  const [publish, setPublish] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (weights.data) {
      setBehavior(weights.data.behavior as NumMap);
      setScoreByGoal(weights.data.score_by_goal as Record<string, NumMap>);
    }
  }, [weights.data]);
  if (weights.isLoading) return <PageSkeleton />;
  if (weights.isError || !weights.data)
    return <ErrorState error={weights.error} onRetry={() => weights.refetch()} />;

  const save = async () => {
    setError(null);
    try {
      await m.putWeights.mutateAsync({
        behavior,
        score_by_goal: scoreByGoal,
        change_note: note || tc("draftNote"),
        publish,
      });
      toast({ title: publish ? tc("published") : tc("draftSaved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };
  const versions = weights.data.versions as unknown as VersionLike[];

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={<VersionStatusBadge status={weights.data.status} />}
      />
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("behavior")}</CardTitle>
            <CardDescription>{t("behaviorBody", { version: weights.data.version })}</CardDescription>
          </CardHeader>
          <CardContent>
            <NumberGrid id="b" values={behavior} onChange={setBehavior} />
          </CardContent>
        </Card>
        {Object.entries(scoreByGoal).map(([goal, vals]) => (
          <Card key={goal}>
            <CardHeader>
              <CardTitle>{t("scoreFor", { goal: titleCase(goal) })}</CardTitle>
              <CardDescription>
                {t("sum", {
                  total: Object.values(vals)
                    .reduce((a, x) => a + x, 0)
                    .toFixed(2),
                })}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <NumberGrid
                id={`g-${goal}`}
                values={vals}
                onChange={(v) => setScoreByGoal({ ...scoreByGoal, [goal]: v })}
              />
            </CardContent>
          </Card>
        ))}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <FormField id="note" label={tc("changeNote")} className="flex-1">
            <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
          </FormField>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <Switch checked={publish} onCheckedChange={setPublish} /> {t("publishNow")}
          </label>
          <Button onClick={save} loading={m.putWeights.isPending}>
            {publish ? tc("publish") : tc("saveDraft")}
          </Button>
          <SandboxDialog params={{}} />
        </div>
        <InlineError error={error} />
        <Card>
          <CardHeader>
            <CardTitle>{tc("history")}</CardTitle>
          </CardHeader>
          <CardContent>
            <VersionHistory kind="weights" versions={versions} onChanged={() => weights.refetch()} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
