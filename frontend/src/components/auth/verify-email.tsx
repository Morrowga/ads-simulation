"use client";

import { CheckCircle2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { InlineError } from "@/components/layout/error-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Verifies the e-mail token automatically when present in the URL; otherwise offers to resend. */
export function VerifyEmail() {
  const t = useTranslations("auth.verify");
  const params = useSearchParams();
  const token = params.get("token");
  const { refetchMe, token: accessToken } = useAuth();
  const [state, setState] = useState<"idle" | "working" | "done" | "error">(token ? "working" : "idle");
  const [error, setError] = useState<unknown>(null);
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    post("/auth/verify-email", { token })
      .then(() => {
        setState("done");
        if (accessToken) void refetchMe();
      })
      .catch((e: unknown) => {
        setError(e);
        setState("error");
      });
  }, [token, accessToken, refetchMe]);

  const resend = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(null);
    try {
      await post("/auth/resend-verification", { email });
      setResent(true);
    } catch (e) {
      setError(e);
    }
  };

  if (state === "working") {
    return (
      <AuthCard title={t("title")} description={t("verifying")}>
        <p className="sr-only" aria-live="polite">
          {t("verifying")}
        </p>
      </AuthCard>
    );
  }
  if (state === "done") {
    return (
      <AuthCard title={t("title")}>
        <Alert variant="success">
          <CheckCircle2 aria-hidden />
          <AlertTitle>{t("doneTitle")}</AlertTitle>
          <AlertDescription>{t("doneBody")}</AlertDescription>
        </Alert>
        <Button asChild className="w-full">
          <Link href={accessToken ? "/dashboard" : "/login"}>
            {accessToken ? t("goDashboard") : t("goLogin")}
          </Link>
        </Button>
      </AuthCard>
    );
  }
  return (
    <AuthCard title={t("title")} description={state === "error" ? t("failed") : t("resendIntro")}>
      <InlineError error={error} />
      <form onSubmit={resend} className="space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="email">{t("email")}</Label>
          <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <Button type="submit" className="w-full" disabled={resent}>
          {resent ? t("resent") : t("resend")}
        </Button>
      </form>
    </AuthCard>
  );
}
