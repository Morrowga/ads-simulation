"use client";

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
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { useAdminMutations, useAdminPlatforms, useAdminPlatformVersions } from "@/lib/queries";
import type { SettingsVersionOut } from "@/lib/types";

type PlatformData = {
  global?: Record<string, unknown>;
  markets?: Record<string, unknown>;
  sources?: Record<string, unknown>;
};

export default function AdminPlatformsPage() {
  const t = useTranslations("admin.platforms");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();
  const platforms = useAdminPlatforms();
  const m = useAdminMutations();
  const [code, setCode] = useState<string | null>(null);
  const versions = useAdminPlatformVersions(code);
  const [selected, setSelected] = useState<SettingsVersionOut | null>(null);
  const [name, setName] = useState("");
  const [status, setStatus] = useState<"full" | "beta" | "planned">("full");
  const [active, setActive] = useState(true);
  const [global, setGlobal] = useState<Record<string, unknown> | null>({});
  const [markets, setMarkets] = useState<Record<string, unknown> | null>({});
  const [sources, setSources] = useState<Record<string, unknown> | null>({});
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!code && platforms.data?.length) setCode(platforms.data[0].code);
  }, [platforms.data, code]);
  useEffect(() => {
    const p = platforms.data?.find((x) => x.code === code);
    if (p) {
      setName(p.name);
      setStatus(p.status);
      setActive(p.active);
    }
    if (versions.data?.length) {
      const v = versions.data.find((x) => x.status === "published") ?? versions.data[0];
      setSelected(v);
      const d = (v.data ?? {}) as PlatformData;
      setGlobal(d.global ?? {});
      setMarkets(d.markets ?? {});
      setSources(d.sources ?? {});
    }
  }, [versions.data, platforms.data, code]);

  const rows = useMemo(
    () =>
      (platforms.data ?? []).map((p) => ({
        code: p.code,
        name: p.name,
        meta: `v${p.current_version ?? "—"}`,
        badges: [
          {
            label: t(`status.${p.status}`),
            variant:
              p.status === "full"
                ? ("success" as const)
                : p.status === "beta"
                  ? ("warning" as const)
                  : ("neutral" as const),
          },
          ...(p.active ? [] : [{ label: t("inactive"), variant: "neutral" as const }]),
        ],
      })),
    [platforms.data, t],
  );

  const save = async () => {
    if (!code) return;
    setError(null);
    try {
      await m.putPlatform.mutateAsync({
        code,
        body: {
          name,
          status,
          active,
          global: global ?? undefined,
          markets: markets ?? undefined,
          sources: sources ?? undefined,
          change_note: note || tc("draftNote"),
        },
      });
      await versions.refetch();
      toast({ title: t("saved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };

  if (platforms.isLoading) return <PageSkeleton />;
  if (platforms.isError) return <ErrorState error={platforms.error} onRetry={() => platforms.refetch()} />;
  const sourceEntries = Object.entries(sources ?? {}).slice(0, 12);

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <EntityList rows={rows} selected={code} onSelect={setCode} label={t("title")} />
        <div className="space-y-4">
          {code ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  {name} {selected ? <VersionStatusBadge status={selected.status} /> : null}{" "}
                  {selected ? <Badge variant="neutral">v{selected.version}</Badge> : null}
                </CardTitle>
                <CardDescription>{t("saveNote")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <FormField id="p-name" label={t("name")}>
                    <Input id="p-name" value={name} onChange={(e) => setName(e.target.value)} />
                  </FormField>
                  <FormField id="p-status" label={t("statusLabel")}>
                    <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
                      <SelectTrigger id="p-status">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(["full", "beta", "planned"] as const).map((s) => (
                          <SelectItem key={s} value={s}>
                            {t(`status.${s}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormField>
                  <label className="flex items-center gap-2 self-end pb-2 text-sm">
                    <Switch checked={active} onCheckedChange={setActive} /> {t("active")}
                  </label>
                </div>
                {sourceEntries.length > 0 ? (
                  <div>
                    <p className="mb-1 text-sm font-medium">{t("sources")}</p>
                    <ul className="flex flex-wrap gap-2">
                      {sourceEntries.map(([k, v]) => (
                        <li key={k} className="rounded-md border border-border px-2 py-1 text-xs">
                          {k}: <Badge variant="neutral">{String(v)}</Badge>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <Tabs defaultValue="global">
                  <TabsList>
                    <TabsTrigger value="global">{t("global")}</TabsTrigger>
                    <TabsTrigger value="markets">{t("markets")}</TabsTrigger>
                    <TabsTrigger value="sources">{t("sources")}</TabsTrigger>
                  </TabsList>
                  <TabsContent value="global">
                    <JsonEditor
                      id="p-global"
                      label={t("global")}
                      value={(selected?.data as PlatformData | undefined)?.global ?? {}}
                      onChange={setGlobal}
                    />
                  </TabsContent>
                  <TabsContent value="markets">
                    <JsonEditor
                      id="p-markets"
                      label={t("markets")}
                      value={(selected?.data as PlatformData | undefined)?.markets ?? {}}
                      onChange={setMarkets}
                    />
                  </TabsContent>
                  <TabsContent value="sources">
                    <JsonEditor
                      id="p-sources"
                      label={t("sources")}
                      value={(selected?.data as PlatformData | undefined)?.sources ?? {}}
                      onChange={setSources}
                      rows={10}
                    />
                  </TabsContent>
                </Tabs>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <FormField id="note" label={tc("changeNote")} className="flex-1">
                    <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
                  </FormField>
                  <Button
                    onClick={save}
                    loading={m.putPlatform.isPending}
                    disabled={!global || !markets || !sources}
                  >
                    {t("save")}
                  </Button>
                  <SandboxDialog params={{ platform_codes: code ? [code] : undefined }} />
                </div>
                <InlineError error={error} />
              </CardContent>
            </Card>
          ) : null}
          {versions.data ? (
            <Card>
              <CardHeader>
                <CardTitle>{tc("history")}</CardTitle>
              </CardHeader>
              <CardContent>
                <VersionHistory
                  kind="platforms"
                  versions={versions.data}
                  selectedId={selected?.id}
                  onSelect={(v) => {
                    const full = versions.data?.find((x) => x.id === v.id);
                    if (full) {
                      setSelected(full);
                      const d = (full.data ?? {}) as PlatformData;
                      setGlobal(d.global ?? {});
                      setMarkets(d.markets ?? {});
                      setSources(d.sources ?? {});
                    }
                  }}
                  onChanged={() => {
                    versions.refetch();
                    platforms.refetch();
                  }}
                />
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </>
  );
}
