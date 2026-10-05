"use client";

import { Plus, Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { JsonEditor } from "@/components/admin/json-editor";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toaster";
import { formatDateTime } from "@/lib/format";
import { useAdminMutations, useAdminSettings } from "@/lib/queries";

interface Account {
  provider: string;
  account_name: string;
  account_number: string;
  note?: string;
}

export default function AdminSettingsPage() {
  const t = useTranslations("admin.settings");
  const locale = useLocale();
  const { toast } = useToast();
  const settings = useAdminSettings();
  const m = useAdminMutations();
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [advanced, setAdvanced] = useState<Record<string, unknown> | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (settings.data) {
      setValues(settings.data.values);
      setAdvanced(settings.data.values);
    }
  }, [settings.data]);
  if (settings.isLoading) return <PageSkeleton />;
  if (settings.isError || !settings.data)
    return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;

  const manual = (values.manual_payment ?? {}) as {
    accounts?: Account[];
    instructions?: string;
    expiry_hours?: number;
  };
  const social = (values.social_links ?? {}) as Record<string, string>;
  const rateLimits = (values.rate_limits ?? {}) as Record<string, number>;
  const set = (k: string, v: unknown) => setValues((s) => ({ ...s, [k]: v }));
  const setManual = (patch: Partial<typeof manual>) => set("manual_payment", { ...manual, ...patch });
  const accounts = manual.accounts ?? [];

  const save = async (payload: Record<string, unknown>) => {
    setError(null);
    try {
      await m.putSettings.mutateAsync({ values: payload, change_note: note || t("defaultNote") });
      toast({ title: t("saved"), variant: "success" });
      setNote("");
    } catch (e) {
      setError(e);
    }
  };

  return (
    <>
      <PageHeader
        title={t("title")}
        description={
          settings.data.updated_at
            ? t("updated", { date: formatDateTime(settings.data.updated_at, locale) })
            : t("description")
        }
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("trial.title")}</CardTitle>
            <CardDescription>{t("trial.body")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <Switch
                id="trial_enabled"
                checked={values.trial_enabled === true}
                onCheckedChange={(v) => set("trial_enabled", v)}
              />
              <label htmlFor="trial_enabled" className="text-sm">
                {t("trial.enabled")}
              </label>
            </div>
            <FormField id="trial_tier" label={t("trial.tier")}>
              <Input
                id="trial_tier"
                value={String(values.trial_tier ?? "standard")}
                onChange={(e) => set("trial_tier", e.target.value)}
                className="sm:w-48"
              />
            </FormField>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField id="trial_ip" label={t("trial.ipLimit")}>
                <Input
                  id="trial_ip"
                  type="number"
                  min={0}
                  value={Number(values.trial_ip_limit_per_day ?? 3)}
                  onChange={(e) => set("trial_ip_limit_per_day", Number(e.target.value))}
                />
              </FormField>
              <FormField id="trial_device" label={t("trial.deviceLimit")}>
                <Input
                  id="trial_device"
                  type="number"
                  min={0}
                  value={Number(values.trial_device_limit_per_day ?? 2)}
                  onChange={(e) => set("trial_device_limit_per_day", Number(e.target.value))}
                />
              </FormField>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("rate.title")}</CardTitle>
            <CardDescription>{t("rate.body")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {Object.entries(rateLimits).map(([k, v]) => (
              <FormField key={k} id={`rl-${k}`} label={k.replace(/_/g, " ")}>
                <Input
                  id={`rl-${k}`}
                  type="number"
                  min={0}
                  value={v}
                  onChange={(e) => set("rate_limits", { ...rateLimits, [k]: Number(e.target.value) })}
                />
              </FormField>
            ))}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("manual.title")}</CardTitle>
            <CardDescription>{t("manual.body")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {accounts.map((a, i) => (
              <div
                key={i}
                className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-[1fr_1fr_1fr_1fr_auto]"
              >
                <Input
                  value={a.provider}
                  placeholder={t("manual.provider")}
                  aria-label={t("manual.provider")}
                  onChange={(e) =>
                    setManual({
                      accounts: accounts.map((x, j) => (j === i ? { ...x, provider: e.target.value } : x)),
                    })
                  }
                />
                <Input
                  value={a.account_name}
                  placeholder={t("manual.accountName")}
                  aria-label={t("manual.accountName")}
                  onChange={(e) =>
                    setManual({
                      accounts: accounts.map((x, j) =>
                        j === i ? { ...x, account_name: e.target.value } : x,
                      ),
                    })
                  }
                />
                <Input
                  value={a.account_number}
                  placeholder={t("manual.accountNumber")}
                  aria-label={t("manual.accountNumber")}
                  onChange={(e) =>
                    setManual({
                      accounts: accounts.map((x, j) =>
                        j === i ? { ...x, account_number: e.target.value } : x,
                      ),
                    })
                  }
                />
                <Input
                  value={a.note ?? ""}
                  placeholder={t("manual.note")}
                  aria-label={t("manual.note")}
                  onChange={(e) =>
                    setManual({
                      accounts: accounts.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)),
                    })
                  }
                />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("manual.remove")}
                  onClick={() => setManual({ accounts: accounts.filter((_x, j) => j !== i) })}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            ))}
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setManual({
                  accounts: [...accounts, { provider: "", account_name: "", account_number: "", note: "" }],
                })
              }
            >
              <Plus aria-hidden /> {t("manual.add")}
            </Button>
            <FormField id="instructions" label={t("manual.instructions")}>
              <Textarea
                id="instructions"
                value={manual.instructions ?? ""}
                onChange={(e) => setManual({ instructions: e.target.value })}
                rows={3}
              />
            </FormField>
            <FormField id="expiry" label={t("manual.expiry")}>
              <Input
                id="expiry"
                type="number"
                min={1}
                value={manual.expiry_hours ?? 48}
                onChange={(e) => setManual({ expiry_hours: Number(e.target.value) })}
                className="sm:w-32"
              />
            </FormField>
            <div>
              <p className="mb-2 text-sm font-medium">{t("manual.social")}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(social).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <Input value={k} readOnly aria-label={t("manual.socialName")} className="w-32" />
                    <Input
                      value={v}
                      aria-label={t("manual.socialUrl", { name: k })}
                      onChange={(e) => set("social_links", { ...social, [k]: e.target.value })}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("manual.remove")}
                      onClick={() => {
                        const { [k]: _gone, ...rest } = social;
                        set("social_links", rest);
                      }}
                    >
                      <Trash2 aria-hidden />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                {["facebook", "messenger", "viber", "telegram"]
                  .filter((k) => !(k in social))
                  .map((k) => (
                    <Button
                      key={k}
                      variant="outline"
                      size="sm"
                      onClick={() => set("social_links", { ...social, [k]: "" })}
                    >
                      <Plus aria-hidden /> {k}
                    </Button>
                  ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>{t("advanced.title")}</CardTitle>
            <CardDescription>{t("advanced.body")}</CardDescription>
          </CardHeader>
          <CardContent>
            <JsonEditor
              id="advanced"
              label={t("advanced.title")}
              value={values}
              onChange={setAdvanced}
              rows={16}
            />
            <Button
              className="mt-3"
              variant="outline"
              onClick={() => advanced && save(advanced)}
              disabled={!advanced}
              loading={m.putSettings.isPending}
            >
              {t("advanced.save")}
            </Button>
          </CardContent>
        </Card>
      </div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end">
        <FormField id="note" label={t("changeNote")} className="flex-1">
          <Input id="note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
        </FormField>
        <Button onClick={() => save(values)} loading={m.putSettings.isPending}>
          {t("save")}
        </Button>
      </div>
      <InlineError error={error} />
    </>
  );
}
