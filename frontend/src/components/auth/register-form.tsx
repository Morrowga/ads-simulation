"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { MailCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { AuthCard } from "@/components/auth/auth-card";
import { InlineError } from "@/components/layout/error-state";
import { FormField, describedBy } from "@/components/layout/form-field";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Link } from "@/i18n/navigation";
import { post } from "@/lib/api";
import { useCountries } from "@/lib/queries";
import { registerSchema, type RegisterValues } from "@/lib/schemas";
import type { RegisterOut } from "@/lib/types";

export function RegisterForm() {
  const t = useTranslations("auth");
  const locale = useLocale();
  const countries = useCountries();
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<RegisterOut | null>(null);
  const [resent, setResent] = useState(false);
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirm: "",
      country: "",
      terms: undefined as unknown as true,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const out = await post<RegisterOut>("/auth/register", {
        name: values.name,
        email: values.email,
        password: values.password,
        country: values.country || null,
        locale,
      });
      setDone(out);
    } catch (e) {
      setError(e);
    }
  });

  const resend = async () => {
    if (!done) return;
    try {
      await post("/auth/resend-verification", { email: done.email });
      setResent(true);
    } catch (e) {
      setError(e);
    }
  };

  if (done) {
    return (
      <AuthCard
        title={t("register.checkEmailTitle")}
        description={t("register.checkEmailBody", { email: done.email })}
      >
        <Alert variant="info">
          <MailCheck aria-hidden />
          <AlertTitle>{t("register.verificationSent")}</AlertTitle>
          <AlertDescription>{done.message}</AlertDescription>
        </Alert>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button asChild className="flex-1">
            <Link href="/login">{t("register.goLogin")}</Link>
          </Button>
          <Button variant="outline" onClick={resend} disabled={resent} className="flex-1">
            {resent ? t("register.resent") : t("register.resend")}
          </Button>
        </div>
        <InlineError error={error} />
      </AuthCard>
    );
  }

  const e = form.formState.errors;
  return (
    <AuthCard
      title={t("register.title")}
      description={t("register.description")}
      footer={
        <>
          {t("register.haveAccount")}{" "}
          <Link href="/login" className="text-primary underline-offset-4 hover:underline">
            {t("register.login")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <FormField id="name" label={t("fields.name")} error={e.name} required>
          <Input
            id="name"
            autoComplete="name"
            aria-invalid={!!e.name}
            aria-describedby={describedBy("name", e.name)}
            {...form.register("name")}
          />
        </FormField>
        <FormField id="email" label={t("fields.email")} error={e.email} required>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!e.email}
            aria-describedby={describedBy("email", e.email)}
            {...form.register("email")}
          />
        </FormField>
        <FormField id="country" label={t("fields.country")} error={e.country} help={t("fields.countryHelp")}>
          <Controller
            control={form.control}
            name="country"
            render={({ field }) => (
              <Select value={field.value ?? ""} onValueChange={field.onChange}>
                <SelectTrigger id="country" aria-describedby="country-help">
                  <SelectValue placeholder={t("fields.countryPlaceholder")} />
                </SelectTrigger>
                <SelectContent>
                  {(countries.data ?? []).map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>
        <FormField
          id="password"
          label={t("fields.password")}
          error={e.password}
          help={t("fields.passwordHelp")}
          required
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!e.password}
            aria-describedby={describedBy("password", e.password, true)}
            {...form.register("password")}
          />
        </FormField>
        <FormField id="confirm" label={t("fields.confirmPassword")} error={e.confirm} required>
          <Input
            id="confirm"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!e.confirm}
            aria-describedby={describedBy("confirm", e.confirm)}
            {...form.register("confirm")}
          />
        </FormField>
        <FormField id="terms" label="" error={e.terms}>
          <div className="flex items-start gap-3">
            <Controller
              control={form.control}
              name="terms"
              render={({ field }) => (
                <Checkbox
                  id="terms"
                  checked={field.value === true}
                  onCheckedChange={(v) => field.onChange(v === true ? true : undefined)}
                  aria-invalid={!!e.terms}
                  className="mt-0.5"
                />
              )}
            />
            <label htmlFor="terms" className="text-sm leading-snug">
              {t.rich("register.terms", {
                link: (chunks) => (
                  <Link
                    href="/legal"
                    className="text-primary underline-offset-4 hover:underline"
                    target="_blank"
                  >
                    {chunks}
                  </Link>
                ),
              })}
            </label>
          </div>
        </FormField>
        <InlineError error={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          {t("register.submit")}
        </Button>
      </form>
    </AuthCard>
  );
}
