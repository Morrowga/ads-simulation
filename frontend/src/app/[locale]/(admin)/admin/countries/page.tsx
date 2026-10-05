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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toaster";
import { useAdminCountries, useAdminCountryVersions, useAdminMutations } from "@/lib/queries";
import type { SettingsVersionOut } from "@/lib/types";

interface LangGroup {
  code: string;
  name: string;
  share: number;
  source?: string;
}

export default function AdminCountriesPage() {
  const t = useTranslations("admin.countries");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();
  const countries = useAdminCountries();
  const m = useAdminMutations();
  const [code, setCode] = useState<string | null>(null);
  const versions = useAdminCountryVersions(code);
  const [selected, setSelected] = useState<SettingsVersionOut | null>(null);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [creating, setCreating] = useState(false);
  const [newC, setNewC] = useState({
    code: "",
    name: "",
    currency: "",
    manual: false,
    card: true,
    active: true,
  });

  useEffect(() => {
    if (!code && countries.data?.length) setCode(countries.data[0].code);
  }, [countries.data, code]);
  useEffect(() => {
    if (versions.data?.length) {
      const draft =
        versions.data.find((v) => v.status === "draft") ??
        versions.data.find((v) => v.status === "published") ??
        versions.data[0];
      setSelected(draft);
      setData((draft.data as Record<string, unknown>) ?? {});
      const c = countries.data?.find((x) => x.code === code);
      setName(c?.name ?? "");
    }
  }, [versions.data, countries.data, code]);

  const rows = useMemo(
    () =>
      (countries.data ?? []).map((c) => ({
        code: c.code,
        name: c.name,
        meta: `${c.currency} · ${c.payment_methods.join(", ")} · v${c.current_version ?? "—"}`,
        badges: [
          ...(c.active ? [] : [{ label: t("inactive"), variant: "neutral" as const }]),
          ...((c.versions as { status: string }[]).some((v) => v.status === "draft")
            ? [{ label: tc("versionStatus.draft"), variant: "warning" as const }]
            : []),
        ],
      })),
    [countries.data, t, tc],
  );

  const saveDraft = async () => {
    if (!code || !data) return;
    setError(null);
    try {
      await m.updateCountry.mutateAsync({
        code,
        body: { name: name || null, data, change_note: note || tc("draftNote") },
      });
      await versions.refetch();
      toast({ title: tc("draftSaved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };
  const create = async () => {
    setError(null);
    try {
      const methods = [...(newC.card ? ["card"] : []), ...(newC.manual ? ["manual"] : [])];
      await m.createCountry.mutateAsync({
        code: newC.code.toUpperCase(),
        name: newC.name,
        currency: newC.currency.toUpperCase(),
        payment_methods: methods,
        active: newC.active,
        data: { languages: [], language_groups: [] },
        change_note: tc("draftNote"),
      });
      setCreating(false);
      setCode(newC.code.toUpperCase());
      toast({ title: tc("draftSaved"), variant: "success" });
    } catch (e) {
      setError(e);
    }
  };

  if (countries.isLoading) return <PageSkeleton />;
  if (countries.isError) return <ErrorState error={countries.error} onRetry={() => countries.refetch()} />;
  const groups = ((data?.language_groups as LangGroup[] | undefined) ?? []).slice(0, 8);

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
          {versions.isLoading ? <PageSkeleton rows={2} /> : null}
          {selected && data ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    {code} · v{selected.version} <VersionStatusBadge status={selected.status} />
                  </CardTitle>
                  <CardDescription>
                    {selected.status === "draft" ? t("editingDraft") : t("editingPublished")}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField id="name" label={t("name")}>
                    <Input
                      id="name"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="sm:w-72"
                    />
                  </FormField>
                  {groups.length > 0 ? (
                    <div>
                      <p className="mb-1 text-sm font-medium">{t("languageGroups")}</p>
                      <ul className="flex flex-wrap gap-2">
                        {groups.map((g) => (
                          <li key={g.code} className="rounded-md border border-border px-2 py-1 text-xs">
                            {g.name} · {Math.round((g.share ?? 0) * 100)}%{" "}
                            {g.source ? <Badge variant="neutral">{g.source}</Badge> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <JsonEditor
                    id="country-data"
                    label={t("data")}
                    value={selected.data ?? {}}
                    onChange={setData}
                  />
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <FormField id="note" label={tc("changeNote")} className="flex-1">
                      <Input
                        id="note"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        maxLength={300}
                      />
                    </FormField>
                    <Button onClick={saveDraft} loading={m.updateCountry.isPending} disabled={!data}>
                      {tc("saveDraft")}
                    </Button>
                    <SandboxDialog params={{ country_code: code ?? undefined }} />
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
                    kind="countries"
                    versions={versions.data ?? []}
                    selectedId={selected.id}
                    onSelect={(v) => {
                      const full = versions.data?.find((x) => x.id === v.id);
                      if (full) {
                        setSelected(full);
                        setData((full.data as Record<string, unknown>) ?? {});
                      }
                    }}
                    onChanged={() => {
                      versions.refetch();
                      countries.refetch();
                    }}
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
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField id="nc-code" label={t("code")} required>
              <Input
                id="nc-code"
                value={newC.code}
                maxLength={2}
                onChange={(e) => setNewC({ ...newC, code: e.target.value })}
              />
            </FormField>
            <FormField id="nc-currency" label={t("currency")} required>
              <Input
                id="nc-currency"
                value={newC.currency}
                maxLength={3}
                onChange={(e) => setNewC({ ...newC, currency: e.target.value })}
              />
            </FormField>
            <FormField id="nc-name" label={t("name")} required className="sm:col-span-2">
              <Input
                id="nc-name"
                value={newC.name}
                onChange={(e) => setNewC({ ...newC, name: e.target.value })}
              />
            </FormField>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={newC.card} onCheckedChange={(v) => setNewC({ ...newC, card: v })} />{" "}
              {t("methodCard")}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={newC.manual} onCheckedChange={(v) => setNewC({ ...newC, manual: v })} />{" "}
              {t("methodManual")}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Switch checked={newC.active} onCheckedChange={(v) => setNewC({ ...newC, active: v })} />{" "}
              {t("active")}
            </label>
          </div>
          <InlineError error={error} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={create}
              loading={m.createCountry.isPending}
              disabled={newC.code.length !== 2 || !newC.name || newC.currency.length !== 3}
            >
              {tc("createDraft")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
