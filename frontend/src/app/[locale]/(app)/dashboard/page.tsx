"use client";

import { Gift, MailWarning, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { TestList } from "@/components/tests/test-list";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link } from "@/i18n/navigation";
import { post } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const t = useTranslations("dashboard");
  const { me } = useAuth();
  const { toast } = useToast();
  const msg = useApiError();
  const [sent, setSent] = useState(false);

  const resend = async () => {
    if (!me) return;
    try {
      await post("/auth/resend-verification", { email: me.email });
      setSent(true);
      toast({ title: t("verifySent"), variant: "success" });
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  return (
    <>
      <PageHeader
        title={t("title", { name: me?.name?.split(" ")[0] ?? "" })}
        description={t("description")}
        actions={
          <Button asChild>
            <Link href="/tests/new">
              <Plus aria-hidden /> {t("newTest")}
            </Link>
          </Button>
        }
      />
      {me && !me.email_verified ? (
        <Alert variant="warning" className="mb-6">
          <MailWarning aria-hidden />
          <AlertTitle>{t("verifyTitle")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{t("verifyBody")}</span>
            <Button size="sm" variant="outline" onClick={resend} disabled={sent}>
              {sent ? t("verifySentShort") : t("verifyResend")}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      {me?.trial_available && me.trial_enabled ? (
        <Alert variant="info" className="mb-6">
          <Gift aria-hidden />
          <AlertTitle>{t("trialTitle")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{t("trialBody")}</span>
            <Button size="sm" asChild>
              <Link href="/tests/new">{t("trialCta")}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      <TestList />
    </>
  );
}
