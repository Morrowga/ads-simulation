"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { AuthCard } from "@/components/auth/auth-card";
import { InlineError } from "@/components/layout/error-state";
import { FormField, describedBy } from "@/components/layout/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { loginSchema, type LoginValues } from "@/lib/schemas";

export function LoginForm() {
  const t = useTranslations("auth");
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<unknown>(null);
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      const out = await login(values.email, values.password);
      const next = params.get("next");
      const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : null;
      router.push(safeNext ?? (out.role === "admin" ? "/admin" : "/dashboard"));
    } catch (e) {
      setError(e);
    }
  });

  return (
    <AuthCard
      title={t("login.title")}
      description={t("login.description")}
      footer={
        <>
          {t("login.noAccount")}{" "}
          <Link href="/register" className="text-primary underline-offset-4 hover:underline">
            {t("login.register")}
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <FormField id="email" label={t("fields.email")} error={form.formState.errors.email} required>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!form.formState.errors.email}
            aria-describedby={describedBy("email", form.formState.errors.email)}
            {...form.register("email")}
          />
        </FormField>
        <FormField
          id="password"
          label={t("fields.password")}
          error={form.formState.errors.password}
          required
          hint={
            <Link href="/forgot-password" className="text-primary underline-offset-4 hover:underline">
              {t("login.forgot")}
            </Link>
          }
        >
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!form.formState.errors.password}
            aria-describedby={describedBy("password", form.formState.errors.password)}
            {...form.register("password")}
          />
        </FormField>
        <InlineError error={error} />
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          {t("login.submit")}
        </Button>
      </form>
    </AuthCard>
  );
}
