"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import type { z } from "zod";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { InlineError } from "@/components/layout/error-state";
import { FormField } from "@/components/layout/form-field";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { usePathname, useRouter } from "@/i18n/navigation";
import { locales, type Locale } from "@/i18n/routing";
import { del, patch, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isAppError } from "@/lib/errors";
import { useCountries } from "@/lib/queries";
import { changePasswordSchema } from "@/lib/schemas";
import type { MeOut } from "@/lib/types";

const LOCALE_NAMES: Record<Locale, string> = { en: "English", th: "ไทย (Thai)" };

export default function SettingsPage() {
  const t = useTranslations("settings");
  const { me, refetchMe, logout } = useAuth();
  const { toast } = useToast();
  const msg = useApiError();
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const countries = useCountries();

  // --- profile
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  useEffect(() => {
    if (me) {
      setName(me.name);
      setCountry(me.country ?? "");
    }
  }, [me]);
  const saveProfile = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setSavingProfile(true);
    try {
      await patch<MeOut>("/me", { name, country: country || null });
      await refetchMe();
      toast({ title: t("profile.saved"), variant: "success" });
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    } finally {
      setSavingProfile(false);
    }
  };

  // --- language
  const changeLocale = async (next: string) => {
    try {
      await patch<MeOut>("/me", { locale: next });
      await refetchMe();
    } catch {
      // the interface language still switches locally
    }
    router.replace(pathname, { locale: next as Locale });
  };

  // --- password (POST /auth/change-password; falls back to a reset link when the endpoint is absent)
  const [pwError, setPwError] = useState<unknown>(null);
  const [pwFallback, setPwFallback] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const pwForm = useForm<z.infer<typeof changePasswordSchema>>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const changePassword = pwForm.handleSubmit(async (v) => {
    setPwError(null);
    try {
      await post("/auth/change-password", {
        current_password: v.current_password,
        new_password: v.new_password,
      });
      pwForm.reset();
      toast({ title: t("password.changed"), variant: "success" });
    } catch (e) {
      if (isAppError(e) && e.status === 404) setPwFallback(true);
      else setPwError(e);
    }
  });
  const sendReset = async () => {
    if (!me) return;
    try {
      await post("/auth/forgot-password", { email: me.email });
      setResetSent(true);
    } catch (e) {
      setPwError(e);
    }
  };

  // --- delete account
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const deleteAccount = async () => {
    setDeleting(true);
    try {
      await del("/me");
      await logout();
      router.push("/");
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
      setDeleting(false);
    }
  };

  const pe = pwForm.formState.errors;
  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("profile.title")}</CardTitle>
            <CardDescription>{me?.email}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={saveProfile} className="space-y-4">
              <FormField id="name" label={t("profile.name")} required>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={120}
                />
              </FormField>
              <FormField id="country" label={t("profile.country")} help={t("profile.countryHelp")}>
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger id="country">
                    <SelectValue placeholder={t("profile.countryPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {(countries.data ?? []).map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormField>
              <Button type="submit" loading={savingProfile}>
                {t("save")}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("language.title")}</CardTitle>
            <CardDescription>{t("language.description")}</CardDescription>
          </CardHeader>
          <CardContent>
            <FormField id="locale" label={t("language.label")}>
              <Select value={locale} onValueChange={changeLocale}>
                <SelectTrigger id="locale" className="sm:w-64">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {locales.map((l) => (
                    <SelectItem key={l} value={l}>
                      {LOCALE_NAMES[l]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <p className="mt-2 text-xs text-muted-foreground">{t("language.note")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("password.title")}</CardTitle>
            <CardDescription>{t("password.description")}</CardDescription>
          </CardHeader>
          <CardContent>
            {pwFallback ? (
              <div className="space-y-3">
                <Alert variant="info">
                  <AlertDescription>{t("password.fallback")}</AlertDescription>
                </Alert>
                <Button onClick={sendReset} disabled={resetSent} variant="outline">
                  {resetSent ? t("password.resetSent") : t("password.sendReset")}
                </Button>
                <InlineError error={pwError} />
              </div>
            ) : (
              <form onSubmit={changePassword} className="space-y-4" noValidate>
                <Controller
                  control={pwForm.control}
                  name="current_password"
                  render={({ field }) => (
                    <FormField
                      id="current_password"
                      label={t("password.current")}
                      error={pe.current_password}
                      required
                    >
                      <Input
                        id="current_password"
                        type="password"
                        autoComplete="current-password"
                        aria-invalid={!!pe.current_password}
                        {...field}
                      />
                    </FormField>
                  )}
                />
                <Controller
                  control={pwForm.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormField id="new_password" label={t("password.new")} error={pe.new_password} required>
                      <Input
                        id="new_password"
                        type="password"
                        autoComplete="new-password"
                        aria-invalid={!!pe.new_password}
                        {...field}
                      />
                    </FormField>
                  )}
                />
                <Controller
                  control={pwForm.control}
                  name="confirm"
                  render={({ field }) => (
                    <FormField id="confirm" label={t("password.confirm")} error={pe.confirm} required>
                      <Input
                        id="confirm"
                        type="password"
                        autoComplete="new-password"
                        aria-invalid={!!pe.confirm}
                        {...field}
                      />
                    </FormField>
                  )}
                />
                <InlineError error={pwError} />
                <Button type="submit" loading={pwForm.formState.isSubmitting}>
                  {t("password.submit")}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>

        <Card className="border-danger/40">
          <CardHeader>
            <CardTitle>{t("delete.title")}</CardTitle>
            <CardDescription>{t("delete.description")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
              {t("delete.button")}
            </Button>
            <ConfirmDialog
              open={confirmDelete}
              onOpenChange={setConfirmDelete}
              title={t("delete.confirmTitle")}
              description={t("delete.confirmBody")}
              confirmLabel={t("delete.button")}
              destructive
              loading={deleting}
              onConfirm={deleteAccount}
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
