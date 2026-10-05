"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { AuthCard } from "@/components/auth/auth-card";
import { InlineError } from "@/components/layout/error-state";
import { FormField, describedBy } from "@/components/layout/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "@/i18n/navigation";
import { post } from "@/lib/api";
import { forgotSchema, resetSchema } from "@/lib/schemas";

export function ForgotPasswordForm() {
  const t = useTranslations("auth.forgot");
  const tf = useTranslations("auth.fields");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const form = useForm<z.infer<typeof forgotSchema>>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: "" },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await post("/auth/forgot-password", v);
      setSent(true);
    } catch (e) {
      setError(e);
    }
  });
  return (
    <AuthCard
      title={t("title")}
      description={t("description")}
      footer={
        <Link href="/login" className="text-primary underline-offset-4 hover:underline">
          {t("backToLogin")}
        </Link>
      }
    >
      {sent ? (
        <Alert variant="success">
          <AlertDescription>{t("sent")}</AlertDescription>
        </Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormField id="email" label={tf("email")} error={form.formState.errors.email} required>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              aria-invalid={!!form.formState.errors.email}
              aria-describedby={describedBy("email", form.formState.errors.email)}
              {...form.register("email")}
            />
          </FormField>
          <InlineError error={error} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            {t("submit")}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

export function ResetPasswordForm() {
  const t = useTranslations("auth.reset");
  const tf = useTranslations("auth.fields");
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const form = useForm<z.infer<typeof resetSchema>>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: "", confirm: "" },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await post("/auth/reset-password", { token, password: v.password });
      setDone(true);
    } catch (e) {
      setError(e);
    }
  });
  const e = form.formState.errors;
  return (
    <AuthCard
      title={t("title")}
      description={token ? t("description") : t("missingToken")}
      footer={
        <Link href="/login" className="text-primary underline-offset-4 hover:underline">
          {t("backToLogin")}
        </Link>
      }
    >
      {done ? (
        <Alert variant="success">
          <AlertDescription>{t("done")}</AlertDescription>
        </Alert>
      ) : token ? (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <FormField
            id="password"
            label={tf("newPassword")}
            error={e.password}
            help={tf("passwordHelp")}
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
          <FormField id="confirm" label={tf("confirmPassword")} error={e.confirm} required>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              aria-invalid={!!e.confirm}
              aria-describedby={describedBy("confirm", e.confirm)}
              {...form.register("confirm")}
            />
          </FormField>
          <InlineError error={error} />
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
            {t("submit")}
          </Button>
        </form>
      ) : null}
    </AuthCard>
  );
}
