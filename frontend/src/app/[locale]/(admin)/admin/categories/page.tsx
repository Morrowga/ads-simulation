"use client";

import { Eye, Plus, Sparkles } from "lucide-react";
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
import { initialProfileData, ProfileForm } from "@/components/profile/profile-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toaster";
import { useAdminCategories, useAdminMutations } from "@/lib/queries";
import type { CategoryTemplateOut, SettingsVersionOut } from "@/lib/types";

const PARTS = [
  "questions",
  "trait_dimensions",
  "activation_rules",
  "default_mixes",
  "buying_behavior",
  "blockers",
  "trust_signals",
  "comment_topics",
  "typical_goals",
  "analyzer_hints",
  "benchmark_adjustments",
  "calendar",
  "restrictions",
  "country_overrides",
] as const;

export default function AdminCategoriesPage() {
  const t = useTranslations("admin.categories");
  const tc = useTranslations("admin.common");
  const { toast } = useToast();
  const all = useAdminCategories();
  const m = useAdminMutations();
  const [code, setCode] = useState<string | null>(null);
  const [selected, setSelected] = useState<SettingsVersionOut | null>(null);
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [preview, setPreview] = useState(false);
  const [previewData, setPreviewData] = useState<Record<string, unknown>>({});
  const [aiOpen, setAiOpen] = useState(false);
  const [ai, setAi] = useState({ name: "", code: "", parent_code: "", hints: "" });
  const [newOpen, setNewOpen] = useState(false);
  const [newCat, setNewCat] = useState({ code: "", name: "" });

  const byCode = useMemo(() => {
    const map = new Map<string, SettingsVersionOut[]>();
    for (const v of all.data ?? []) {
      const k = v.code ?? v.id;
      map.set(k, [...(map.get(k) ?? []), v]);
    }
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
  useEffect(() => {
    if (versions.length) {
      const v =
        versions.find((x) => x.status === "draft") ??
        versions.find((x) => x.status === "published") ??
        versions[0];
      setSelected(v);
      const d = (v.data as Record<string, unknown>) ?? {};
      setData(d);
      setName(String(d.name ?? ""));
    } else {
      setSelected(null);
      setData(null);
    }
  }, [versions]);

  const rows = codes.map((c) => {
    const vs = byCode.get(c) ?? [];
    const pub = vs.find((v) => v.status === "published");
    return {
      code: c,
      name: String((pub?.data ?? vs[0]?.data ?? {}).name ?? c),
      meta: pub ? `v${pub.version}` : t("noPublished"),
      badges: vs.some((v) => v.status === "draft")
        ? [{ label: tc("versionStatus.draft"), variant: "warning" as const }]
        : [],
    };
  });

  const saveDraft = async () => {
    if (!code || !data) return;
    setError(null);
    try {
      await m.updateCategory.mutateAsync({
        code,
        body: { name: name || null, data, change_note: note || tc("draftNote") },
      });
      toast({ title: tc("draftSaved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };
  const draftAi = async () => {
    setError(null);
    try {
      const out = await m.draftCategoryAi.mutateAsync({
        name: ai.name,
        code: ai.code || null,
        parent_code: ai.parent_code || null,
        hints: ai.hints,
      });
      setAiOpen(false);
      setCode(out.code ?? null);
      toast({ title: t("aiDone"), variant: "success" });
    } catch (e) {
      setError(e);
    }
  };
  const createNew = async () => {
    setError(null);
    try {
      const out = await m.createCategory.mutateAsync({
        code: newCat.code,
        name: newCat.name,
        data: {
          name: newCat.name,
          questions: [],
          trait_dimensions: [],
          comment_topics: ["price", "product_detail", "service", "positive", "negative", "other"],
          typical_goals: ["sales", "messages"],
        },
        change_note: tc("draftNote"),
      });
      setNewOpen(false);
      setCode(out.code ?? null);
    } catch (e) {
      setError(e);
    }
  };

  if (all.isLoading) return <PageSkeleton />;
  if (all.isError) return <ErrorState error={all.error} onRetry={() => all.refetch()} />;
  const template = data
    ? ({
        code: code ?? "",
        name,
        parent_code: null,
        tags: [],
        version: selected?.version ?? 0,
        status: "draft",
        questions: (data.questions as CategoryTemplateOut["questions"]) ?? [],
        trait_dimensions: [],
        activation_rules: [],
        default_mixes: {},
        buying_behavior: {},
        blockers: [],
        trust_signals: [],
        comment_topics: [],
        typical_goals: [],
        analyzer_hints: {},
        benchmark_adjustments: {},
        calendar: {},
        restrictions: {},
        country_overrides: {},
      } as CategoryTemplateOut)
    : null;

  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <>
            <Button variant="outline" onClick={() => setNewOpen(true)}>
              <Plus aria-hidden /> {t("new")}
            </Button>
            <Button onClick={() => setAiOpen(true)}>
              <Sparkles aria-hidden /> {t("draftAi")}
            </Button>
          </>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <EntityList rows={rows} selected={code} onSelect={setCode} label={t("title")} />
        <div className="space-y-4">
          {selected && data ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2">
                    {code} · v{selected.version} <VersionStatusBadge status={selected.status} />
                    <Badge variant="neutral">
                      {t("questionCount", { count: ((data.questions as unknown[]) ?? []).length })}
                    </Badge>
                  </CardTitle>
                  <CardDescription>{t("partsHint")}</CardDescription>
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
                  <Tabs defaultValue="all">
                    <TabsList className="h-auto flex-wrap">
                      <TabsTrigger value="all">{t("allParts")}</TabsTrigger>
                      {PARTS.map((p) => (
                        <TabsTrigger key={p} value={p}>
                          {p.replace(/_/g, " ")}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    <TabsContent value="all">
                      <JsonEditor
                        id="cat-all"
                        label={t("allParts")}
                        value={selected.data ?? {}}
                        onChange={(v) => v && setData(v)}
                        rows={22}
                      />
                    </TabsContent>
                    {PARTS.map((p) => (
                      <TabsContent key={p} value={p}>
                        <PartEditor
                          id={`cat-${p}`}
                          label={p}
                          value={data[p]}
                          onChange={(v) => setData({ ...data, [p]: v })}
                        />
                      </TabsContent>
                    ))}
                  </Tabs>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                    <FormField id="note" label={tc("changeNote")} className="flex-1">
                      <Input
                        id="note"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        maxLength={300}
                      />
                    </FormField>
                    <Button onClick={saveDraft} loading={m.updateCategory.isPending} disabled={!data}>
                      {tc("saveDraft")}
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setPreviewData(initialProfileData(template ?? undefined, {}));
                        setPreview(true);
                      }}
                    >
                      <Eye aria-hidden /> {t("previewForm")}
                    </Button>
                    <SandboxDialog params={{ category_code: code ?? undefined }} />
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
                    kind="categories"
                    versions={versions}
                    selectedId={selected.id}
                    onSelect={(v) => {
                      const full = versions.find((x) => x.id === v.id);
                      if (full) {
                        setSelected(full);
                        setData((full.data as Record<string, unknown>) ?? {});
                      }
                    }}
                    onChanged={() => all.refetch()}
                  />
                </CardContent>
              </Card>
            </>
          ) : null}
        </div>
      </div>

      <Dialog open={preview} onOpenChange={setPreview}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t("previewTitle", { name })}</DialogTitle>
            <DialogDescription>{t("previewBody")}</DialogDescription>
          </DialogHeader>
          {template ? <ProfileForm template={template} data={previewData} onChange={setPreviewData} /> : null}
        </DialogContent>
      </Dialog>

      <Dialog open={aiOpen} onOpenChange={setAiOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("draftAi")}</DialogTitle>
            <DialogDescription>{t("aiBody")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <FormField id="ai-name" label={t("name")} required>
              <Input id="ai-name" value={ai.name} onChange={(e) => setAi({ ...ai, name: e.target.value })} />
            </FormField>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField id="ai-code" label={t("code")} help={t("codeHelp")}>
                <Input
                  id="ai-code"
                  value={ai.code}
                  onChange={(e) => setAi({ ...ai, code: e.target.value })}
                />
              </FormField>
              <FormField id="ai-parent" label={t("parent")}>
                <Input
                  id="ai-parent"
                  value={ai.parent_code}
                  onChange={(e) => setAi({ ...ai, parent_code: e.target.value })}
                />
              </FormField>
            </div>
            <FormField id="ai-hints" label={t("hints")}>
              <Textarea
                id="ai-hints"
                value={ai.hints}
                onChange={(e) => setAi({ ...ai, hints: e.target.value })}
                rows={3}
              />
            </FormField>
          </div>
          <InlineError error={error} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setAiOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button onClick={draftAi} loading={m.draftCategoryAi.isPending} disabled={!ai.name.trim()}>
              <Sparkles aria-hidden /> {t("generate")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={newOpen} onOpenChange={setNewOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("new")}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <FormField id="new-code" label={t("code")} required>
              <Input
                id="new-code"
                value={newCat.code}
                onChange={(e) => setNewCat({ ...newCat, code: e.target.value })}
              />
            </FormField>
            <FormField id="new-name" label={t("name")} required>
              <Input
                id="new-name"
                value={newCat.name}
                onChange={(e) => setNewCat({ ...newCat, name: e.target.value })}
              />
            </FormField>
          </div>
          <InlineError error={error} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewOpen(false)}>
              {tc("cancel")}
            </Button>
            <Button
              onClick={createNew}
              loading={m.createCategory.isPending}
              disabled={!newCat.code.trim() || !newCat.name.trim()}
            >
              {tc("createDraft")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Editor for one category part; arrays and objects are edited as JSON. */
function PartEditor({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const tc = useTranslations("admin.common");
  const [text, setText] = useState(JSON.stringify(value ?? (Array.isArray(value) ? [] : {}), null, 2));
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => setText(JSON.stringify(value ?? {}, null, 2)), [value]);
  return (
    <div className="space-y-1.5">
      <Textarea
        id={id}
        aria-label={label}
        value={text}
        rows={14}
        spellCheck={false}
        className="font-mono text-xs"
        onChange={(e) => {
          setText(e.target.value);
          try {
            onChange(JSON.parse(e.target.value));
            setErr(null);
          } catch (ex) {
            setErr(ex instanceof Error ? ex.message : tc("jsonInvalid"));
          }
        }}
      />
      {err ? (
        <p role="alert" className="text-xs text-danger">
          {err}
        </p>
      ) : null}
    </div>
  );
}
