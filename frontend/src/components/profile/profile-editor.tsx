"use client";

/** Create/edit a Business Profile: name, category (create only), default flag, dynamic form, version history. */
import { zodResolver } from "@hookform/resolvers/zod";
import { History, Save } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { StatusBadge } from "@/components/layout/status-badge";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import {
  initialProfileData,
  missingRequired,
  ProfileForm,
  type ProfileData,
} from "@/components/profile/profile-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toaster";
import { Link, useRouter } from "@/i18n/navigation";
import { isAppError } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import {
  useCategories,
  useCategory,
  useProfile,
  useProfileMutations,
  useProfileVersions,
} from "@/lib/queries";
import { profileEditMetaSchema, profileMetaSchema, type ProfileMetaValues } from "@/lib/schemas";
import type { TestStatus } from "@/lib/types";

export function ProfileEditor({ profileId, returnTo }: { profileId?: string; returnTo?: string }) {
  const t = useTranslations("profiles");
  const tv = useTranslations("validation");
  const locale = useLocale();
  const router = useRouter();
  const { toast } = useToast();
  const isNew = !profileId;

  const categories = useCategories();
  const existing = useProfile(profileId);
  const versions = useProfileVersions(profileId);
  const { create, update } = useProfileMutations();

  const form = useForm<ProfileMetaValues>({
    resolver: zodResolver(isNew ? profileMetaSchema : profileEditMetaSchema),
    defaultValues: { name: "", category_code: "", is_default: isNew },
  });
  const categoryCode = form.watch("category_code");
  const template = useCategory(categoryCode || existing.data?.category_code);
  const [data, setData] = useState<ProfileData>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [changeNote, setChangeNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (existing.data && !seeded) {
      form.reset({
        name: existing.data.name,
        category_code: existing.data.category_code,
        is_default: existing.data.is_default,
      });
      setData(existing.data.data as ProfileData);
      setSeeded(true);
    }
  }, [existing.data, seeded, form]);

  useEffect(() => {
    if (template.data) setData((d) => initialProfileData(template.data, d));
  }, [template.data]);

  const missing = useMemo(
    () => (template.data ? missingRequired(template.data, data) : []),
    [template.data, data],
  );

  const onSubmit = form.handleSubmit(async (meta) => {
    setError(null);
    if (isNew && missing.length > 0) {
      setFieldErrors(Object.fromEntries(missing.map((k) => [k, tv("required")])));
      return;
    }
    setFieldErrors({});
    try {
      if (isNew) {
        const p = await create.mutateAsync({
          name: meta.name,
          category_code: meta.category_code,
          data,
          is_default: meta.is_default,
        });
        toast({ title: t("created"), variant: "success" });
        router.push(
          returnTo ? `${returnTo}${returnTo.includes("?") ? "&" : "?"}profile=${p.id}` : `/profiles/${p.id}`,
        );
      } else if (profileId) {
        await update.mutateAsync({
          id: profileId,
          body: {
            name: meta.name,
            data,
            is_default: meta.is_default,
            change_note: changeNote || t("defaultChangeNote"),
          },
        });
        setChangeNote("");
        toast({ title: t("saved"), variant: "success" });
        router.push(returnTo ?? "/profiles");
      }
    } catch (e) {
      if (isAppError(e) && e.code === "profile_invalid") {
        setFieldErrors(
          Object.fromEntries(
            Object.entries(e.fieldErrors).map(([k, v]) => [k, v === "required" ? tv("required") : v]),
          ),
        );
      }
      setError(e);
    }
  });

  if (!isNew && existing.isLoading) return <PageSkeleton />;
  if (!isNew && existing.isError)
    return <ErrorState error={existing.error} onRetry={() => existing.refetch()} />;

  const e = form.formState.errors;

  console.log("edit data:", existing.data?.data, "state:", data, "template:", template.data?.code);
  return (
    <form onSubmit={onSubmit} className="space-y-6" noValidate>
      <PageHeader
        title={isNew ? t("newTitle") : t("editTitle", { name: existing.data?.name ?? "" })}
        description={
          isNew ? t("newDescription") : t("editDescription", { version: existing.data?.current_version ?? 1 })
        }
        actions={
          <>
            <Button type="button" variant="outline" asChild>
              <Link href={returnTo ?? "/profiles"}>{t("back")}</Link>
            </Button>
            <Button type="submit" loading={create.isPending || update.isPending} disabled={!template.data}>
              <Save aria-hidden /> {isNew ? t("create") : t("saveVersion")}
            </Button>
          </>
        }
      />
      <Card>
        <CardHeader>
          <CardTitle>{t("presetTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <FormField id="name" label={t("fields.name")} error={e.name} required help={t("fields.nameHelp")}>
            <Input id="name" aria-invalid={!!e.name} {...form.register("name")} />
          </FormField>
          <FormField
            id="category"
            label={t("fields.category")}
            error={e.category_code}
            required={isNew}
            help={isNew ? t("fields.categoryHelp") : t("fields.categoryLocked")}
          >
            {isNew ? (
              <Controller
                control={form.control}
                name="category_code"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="category" aria-invalid={!!e.category_code}>
                      <SelectValue placeholder={t("fields.categoryPlaceholder")} />
                    </SelectTrigger>
                    <SelectContent>
                      {(categories.data ?? []).map((c) => (
                        <SelectItem key={c.code} value={c.code}>
                          {c.parent_code ? `${c.parent_code} → ` : ""}
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            ) : (
              <Input
                id="category"
                value={existing.data?.category_name ?? existing.data?.category_code ?? ""}
                readOnly
                disabled
              />
            )}
          </FormField>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Controller
              control={form.control}
              name="is_default"
              render={({ field }) => (
                <Switch id="is_default" checked={field.value} onCheckedChange={field.onChange} />
              )}
            />
            <label htmlFor="is_default" className="text-sm">
              {t("fields.isDefault")}
            </label>
          </div>
          {!isNew ? (
            <FormField
              id="change_note"
              label={t("fields.changeNote")}
              help={t("fields.changeNoteHelp")}
              className="sm:col-span-2"
            >
              <Input
                id="change_note"
                value={changeNote}
                onChange={(ev) => setChangeNote(ev.target.value)}
                maxLength={200}
              />
            </FormField>
          ) : null}
        </CardContent>
      </Card>

      {template.isLoading ? <PageSkeleton rows={2} /> : null}
      {template.data ? (
        <ProfileForm template={template.data} data={data} onChange={setData} errors={fieldErrors} />
      ) : null}
      {!categoryCode && isNew ? (
        <p className="text-sm text-muted-foreground">{t("pickCategoryFirst")}</p>
      ) : null}
      <InlineError error={error} />

      {!isNew && versions.data ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4" aria-hidden /> {t("history.title")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="relative space-y-4 border-l border-border pl-5">
              {versions.data.map((v) => {
                const tests = (v.tests ?? []) as { id: string; title: string; status: TestStatus }[];
                return (
                  <li key={v.id} className="relative">
                    <span
                      className="absolute -left-[1.6rem] top-1.5 h-2.5 w-2.5 rounded-full bg-primary"
                      aria-hidden
                    />
                    <div className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="font-medium">v{v.version}</span>
                      <span className="text-muted-foreground">{formatDateTime(v.created_at, locale)}</span>
                      {v.version === existing.data?.current_version ? (
                        <Badge variant="info">{t("history.current")}</Badge>
                      ) : null}
                    </div>
                    {tests.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {tests.map((x) => (
                          <li key={x.id} className="flex items-center gap-2 text-sm">
                            <Link href={`/tests/${x.id}`} className="text-primary hover:underline">
                              {x.title}
                            </Link>
                            <StatusBadge status={x.status} />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-1 text-xs text-muted-foreground">{t("history.noTests")}</p>
                    )}
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex justify-end gap-2 border-t border-border pt-4">
        <Button type="button" variant="outline" asChild>
          <Link href={returnTo ?? "/profiles"}>{t("back")}</Link>
        </Button>
        <Button type="submit" loading={create.isPending || update.isPending} disabled={!template.data}>
          <Save aria-hidden /> {isNew ? t("create") : t("saveVersion")}
        </Button>
      </div>
    </form>
  );
}
