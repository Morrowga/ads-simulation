"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { EntityList } from "@/components/admin/entity-list";
import { JsonEditor } from "@/components/admin/json-editor";
import { SandboxDialog } from "@/components/admin/sandbox-dialog";
import { VersionHistory, VersionStatusBadge } from "@/components/admin/version-history";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toaster";
import { useAdminMutations, useAdminScenarios } from "@/lib/queries";
import type { ScenarioOut } from "@/lib/types";

export default function AdminScenariosPage() {
  const t = useTranslations("admin.scenarios");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();
  const all = useAdminScenarios();
  const m = useAdminMutations();
  const [code, setCode] = useState<string | null>(null);
  const [selected, setSelected] = useState<ScenarioOut | null>(null);
  const [name, setName] = useState("");
  const [weight, setWeight] = useState(1);
  const [active, setActive] = useState(true);
  const [countries, setCountries] = useState("");
  const [categories, setCategories] = useState("");
  const [modifiers, setModifiers] = useState<Record<string, unknown> | null>({});
  const [dateRules, setDateRules] = useState<Record<string, unknown> | null>({});
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [creating, setCreating] = useState(false);
  const [newS, setNewS] = useState({ code: "", name: "" });

  const byCode = useMemo(() => {
    const map = new Map<string, ScenarioOut[]>();
    for (const s of all.data ?? []) map.set(s.code, [...(map.get(s.code) ?? []), s]);
    return map;
  }, [all.data]);
  const codes = useMemo(() => Array.from(byCode.keys()).sort(), [byCode]);
  useEffect(() => {
    if (!code && codes.length) setCode(codes[0]);
  }, [codes, code]);
  const versions = useMemo(
    () => (code ? [...(byCode.get(code) ?? [])].sort((a, b) => b.version - a.version) : []),
    [byCode, code],
  );
  const load = (s: ScenarioOut) => {
    setSelected(s);
    setName(s.name);
    setWeight(s.weight);
    setActive(s.active);
    setCountries(s.country_codes.join(", "));
    setCategories(s.category_codes.join(", "));
    setModifiers(s.modifiers);
    setDateRules(s.date_rules);
  };
  useEffect(() => {
    if (versions.length)
      load(
        versions.find((x) => x.status === "draft") ??
          versions.find((x) => x.status === "published") ??
          versions[0],
      );
    else setSelected(null);
  }, [versions]);

  const rows = codes.map((c) => {
    const vs = byCode.get(c) ?? [];
    const pub = vs.find((v) => v.status === "published");
    return {
      code: c,
      name: pub?.name ?? vs[0].name,
      meta: `${t("weight")} ${pub?.weight ?? vs[0].weight} · ${pub ? `v${pub.version}` : t("noPublished")}`,
      badges: [
        ...(vs.some((v) => v.status === "draft")
          ? [{ label: tc("versionStatus.draft"), variant: "warning" as const }]
          : []),
        ...((pub ?? vs[0]).active ? [] : [{ label: t("inactive"), variant: "neutral" as const }]),
      ],
    };
  });

  const save = async () => {
    if (!selected) return;
    setError(null);
    const data = {
      modifiers: modifiers ?? {},
      date_rules: dateRules ?? {},
      weight,
      active,
      country_codes: countries
        .split(",")
        .map((x) => x.trim().toUpperCase())
        .filter(Boolean),
      category_codes: categories
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    };
    try {
      await m.updateScenario.mutateAsync({
        id: selected.id,
        body: { name, data, change_note: note || tc("draftNote") },
      });
      toast({ title: tc("draftSaved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };
  const create = async () => {
    setError(null);
    try {
      const out = await m.createScenario.mutateAsync({
        code: newS.code,
        name: newS.name,
        data: {
          modifiers: {},
          date_rules: {},
          weight: 1,
          active: true,
          country_codes: [],
          category_codes: [],
        },
        change_note: tc("draftNote"),
      });
      setCreating(false);
      setCode(out.code ?? null);
    } catch (e) {
      setError(e);
    }
  };

  if (all.isLoading) return <PageSkeleton />;
  if (all.isError) return <ErrorState error={all.error} onRetry={() => all.refetch()} />;
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden /> {t("new")}
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <EntityList rows={rows} selected={code} onSelect={setCode} label={t("title")} />
        <div className="space-y-4">
          {selected ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    {selected.code} · v{selected.version} <VersionStatusBadge status={selected.status} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <FormField id="s-name" label={t("name")}>
                      <Input id="s-name" value={name} onChange={(e) => setName(e.target.value)} />
                    </FormField>
                    <FormField id="s-weight" label={t("weight")}>
                      <Input
                        id="s-weight"
                        type="number"
                        step="0.1"
                        min={0}
                        value={weight}
                        onChange={(e) => setWeight(Number(e.target.value))}
                      />
                    </FormField>
                    <label className="flex items-center gap-2 self-end pb-2 text-sm">
                      <Switch checked={active} onCheckedChange={setActive} /> {t("active")}
                    </label>
                    <FormField id="s-countries" label={t("countries")} help={t("listHelp")}>
                      <Input
                        id="s-countries"
                        value={countries}
                        onChange={(e) => setCountries(e.target.value)}
                      />
                    </FormField>
                    <FormField id="s-categories" label={t("categories")} help={t("listHelp")}>
                      <Input
                        id="s-categories"
                        value={categories}
                        onChange={(e) => setCategories(e.target.value)}
                      />
                    </FormField>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="mb-1 text-sm font-medium">{t("modifiers")}</p>
                      <JsonEditor
                        id="s-mod"
                        label={t("modifiers")}
                        value={selected.modifiers}
                        onChange={setModifiers}
                        rows={10}
                      />
                    </div>
                    <div>
                      <p className="mb-1 text-sm font-medium">{t("dateRules")}</p>
                      <JsonEditor
                        id="s-dates"
                        label={t("dateRules")}
                        value={selected.date_rules}
                        onChange={setDateRules}
                        rows={10}
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <FormField id="note" label={tc("changeNote")} className="flex-1">
                      <Input
                        id="note"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        maxLength={300}
                      />
                    </FormField>
                    <Button
                      onClick={save}
                      loading={m.updateScenario.isPending}
                      disabled={!modifiers || !dateRules}
                    >
                      {tc("saveDraft")}
                    </Button>
                    <SandboxDialog params={{}} />
                  </div>
                  <InlineError error={error} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>{tc("history")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <VersionHistory
                    kind="scenarios"
                    versions={versions}
                    selectedId={selected.id}
                    onSelect={(v) =>
                      versions.find((x) => x.id === v.id) && load(versions.find((x) => x.id === v.id)!)
                    }
                    onChanged={() => all.refetch()}
                  />
                </CardContent>
              </Card>
            </>
          ) : null}
        </div>
      </div>
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("new")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <FormField id="ns-code" label={t("code")} required>
              <Input
                id="ns-code"
                value={newS.code}
                onChange={(e) => setNewS({ ...newS, code: e.target.value })}
              />
            </FormField>
            <FormField id="ns-name" label={t("name")} required>
              <Input
                id="ns-name"
                value={newS.name}
                onChange={(e) => setNewS({ ...newS, name: e.target.value })}
              />
            </FormField>
          </div>
          <InlineError error={error} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={create}
              loading={m.createScenario.isPending}
              disabled={!newS.code.trim() || !newS.name.trim()}
            >
              {tc("createDraft")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
