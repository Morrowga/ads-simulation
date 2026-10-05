"use client";

import { CreditCard, Gift, Landmark, Loader2, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  ManualOrderDetails,
  recallManualOrder,
  rememberManualOrder,
} from "@/components/checkout/manual-order";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { Money } from "@/components/layout/money";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link, useRouter } from "@/i18n/navigation";
import { get, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isAppError } from "@/lib/errors";
import { titleCase } from "@/lib/format";
import { useCheckout, usePayments, useTest, useTestMutations, useTiers } from "@/lib/queries";
import { STRIPE_MODE } from "@/lib/config";
import type { ManualPaymentOut, TestOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const TIER_ORDER = ["quick", "standard", "full"];

function CheckoutInner() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const stripe = params.get("stripe");
  const t = useTranslations("checkout");
  const router = useRouter();
  const { toast } = useToast();
  const msg = useApiError();
  const { me, refetchMe } = useAuth();

  const test = useTest(id, {
    refetchInterval: (q) => (q.state.data?.status === "payment_review" ? 15_000 : false),
  });
  const checkout = useCheckout(id, {
    enabled:
      !!test.data && (test.data.status === "awaiting_payment" || test.data.status === "payment_review"),
  });
  const payments = usePayments(null);
  const tiersInfo = useTiers(test.data?.country_code ?? null, Math.max(1, test.data?.platforms.length ?? 1));
  const m = useTestMutations(id);

  const [error, setError] = useState<unknown>(null);
  const [manual, setManual] = useState<ManualPaymentOut | null>(null);
  const [polling, setPolling] = useState<"idle" | "polling" | "timeout">("idle");
  const [switching, setSwitching] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  // after a trial refusal (limits, review) the paid methods are shown instead of the banner
  const [trialBlocked, setTrialBlocked] = useState(false);
  const pollStarted = useRef(false);

  useEffect(() => {
    setManual(recallManualOrder(id));
  }, [id]);

  // Stripe return: poll GET /tests/{id} every 2 s (max 60 s) until queued/running
  useEffect(() => {
    if (stripe !== "success" || pollStarted.current) return;
    pollStarted.current = true;
    setPolling("polling");
    let cancelled = false;
    const started = Date.now();
    const tick = async () => {
      try {
        const td = await get<TestOut>(`/tests/${id}`);
        if (cancelled) return;
        if (td.status === "queued" || td.status === "running" || td.status === "completed") {
          router.replace(`/tests/${id}/live`);
          return;
        }
      } catch {
        // keep polling
      }
      if (Date.now() - started > 60_000) {
        setPolling("timeout");
        return;
      }
      setTimeout(tick, 2000);
    };
    void tick();
    return () => {
      cancelled = true;
    };
  }, [stripe, id, router]);

  // Manual order approved meanwhile → test is queued → go live
  useEffect(() => {
    if (test.data && (test.data.status === "queued" || test.data.status === "running"))
      router.replace(`/tests/${id}/live`);
  }, [test.data, id, router]);

  const pendingManual = useMemo(
    () =>
      (payments.data?.items ?? []).find(
        (p) => p.ad_test_id === id && p.method === "manual" && p.status === "pending_review",
      ) ?? null,
    [payments.data, id],
  );
  const lastCancelled = useMemo(
    () =>
      (payments.data?.items ?? []).find(
        (p) =>
          p.ad_test_id === id &&
          p.method === "manual" &&
          (p.status === "cancelled" || p.status === "expired"),
      ) ?? null,
    [payments.data, id],
  );
  const audienceCount = (test.data?.audiences ?? []).length;

  const switchTier = async (code: string) => {
    if (!test.data || code === test.data.tier_code) return;
    setError(null);
    setSwitching(code);
    try {
      await m.update.mutateAsync({ testId: id, body: { tier_code: code } });
      await m.confirm.mutateAsync(id);
      await checkout.refetch();
    } catch (e) {
      setError(e);
    } finally {
      setSwitching(null);
    }
  };

  const payTrial = async () => {
    setError(null);
    try {
      await m.payTrial.mutateAsync(id);
      await refetchMe();
      router.push(`/tests/${id}/live`);
    } catch (e) {
      if (isAppError(e) && (e.code === "trial_review_required" || e.code === "trial_not_available"))
        setTrialBlocked(true);
      setError(e);
    }
  };
  const payCard = async () => {
    setError(null);
    try {
      const out = await m.payCard.mutateAsync(id);
      if (out.checkout_url) {
        window.location.assign(out.checkout_url);
        return;
      }
      if (out.test_status === "queued" || out.test_status === "running") router.push(`/tests/${id}/live`);
      else await test.refetch();
    } catch (e) {
      setError(e);
    }
  };
  const payManual = async () => {
    setError(null);
    try {
      const out = await m.payManual.mutateAsync(id);
      rememberManualOrder(id, out);
      setManual(out);
      await test.refetch();
      toast({ title: t("manual.created"), variant: "success" });
    } catch (e) {
      setError(e);
    }
  };
  const resendVerification = async () => {
    if (!me) return;
    try {
      await post("/auth/resend-verification", { email: me.email });
      setResent(true);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  if (test.isLoading) return <PageSkeleton />;
  if (test.isError || !test.data) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  const td = test.data;

  if (td.status === "draft") {
    return (
      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("needsConfirm")}</span>
          <Button size="sm" asChild>
            <Link href={`/tests/${id}/confirm`}>{t("goConfirm")}</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }
  if (td.status !== "awaiting_payment" && td.status !== "payment_review") {
    return (
      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("alreadyPaid")}</span>
          <Button size="sm" asChild>
            <Link href={`/tests/${id}`}>{t("openTest")}</Link>
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  if (polling === "polling") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 p-10 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" aria-hidden />
          <p className="font-medium" aria-live="polite">
            {t("card.confirming")}
          </p>
          <p className="text-sm text-muted-foreground">{t("card.confirmingBody")}</p>
        </CardContent>
      </Card>
    );
  }

  const info = checkout.data;
  if (checkout.isError) {
    const e = checkout.error;
    if (isAppError(e) && e.code === "duplicate_test") {
      return (
        <Alert variant="destructive">
          <AlertTitle>{t("duplicateTitle")}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{msg(e)}</span>
            <Button size="sm" variant="outline" asChild>
              <Link href={`/tests/${id}/confirm`}>{t("backToConfirm")}</Link>
            </Button>
          </AlertDescription>
        </Alert>
      );
    }
    return <ErrorState error={e} onRetry={() => checkout.refetch()} />;
  }
  if (!info) return <PageSkeleton />;

  const inReview = td.status === "payment_review";
  const useTrialBanner = info.trial_available && info.methods.includes("trial") && !inReview && !trialBlocked;
  const sortedTiers = [...info.tiers].sort((a, b) => TIER_ORDER.indexOf(a.code) - TIER_ORDER.indexOf(b.code));
  const selectedTier = info.tiers.find((x) => x.selected);
  const trialOnlyStandard = info.trial_reason?.startsWith("trial_only_")
    ? info.trial_reason.replace("trial_only_", "")
    : null;
  const cardTabAllowed = info.methods.includes("card");
  const manualTabAllowed = info.methods.includes("manual");
  const defaultTab = manualTabAllowed && !cardTabAllowed ? "manual" : inReview ? "manual" : "card";

  return (
    <div className="space-y-6">
      <PageHeader title={t("title")} description={t("description")} />

      {info.test_mode_banner ? (
        <Alert variant="warning">
          <ShieldCheck aria-hidden />
          <AlertDescription>
            {t("testModeBanner", { mode: info.payment_mode === "mock" ? t("modeMock") : STRIPE_MODE })}
          </AlertDescription>
        </Alert>
      ) : null}
      {stripe === "cancel" ? (
        <Alert variant="warning">
          <AlertDescription>{t("card.cancelled")}</AlertDescription>
        </Alert>
      ) : null}
      {polling === "timeout" ? (
        <Alert variant="info">
          <AlertDescription>{t("card.slow")}</AlertDescription>
        </Alert>
      ) : null}
      {lastCancelled && !pendingManual && !inReview ? (
        <Alert variant="warning">
          <AlertTitle>
            {lastCancelled.status === "expired" ? t("manual.previousExpired") : t("manual.previousCancelled")}
          </AlertTitle>
          <AlertDescription>{lastCancelled.cancel_reason || t("manual.startNew")}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-6">
          {useTrialBanner ? (
            <Card className="border-primary">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gift className="h-5 w-5 text-primary" aria-hidden /> {t("trial.title")}
                </CardTitle>
                <CardDescription>
                  {t("trial.body", { tier: selectedTier?.name ?? "Standard" })}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted-foreground">{t("trial.note")}</p>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button asChild variant="outline" size="lg">
                    <Link href={`/tests/${id}/confirm`}>{t("summary.review")}</Link>
                  </Button>
                  <Button size="lg" onClick={payTrial} loading={m.payTrial.isPending}>
                    {t("trial.run")}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : null}

          {!useTrialBanner && info.trial_reason === "email_not_verified" ? (
            <Alert variant="info">
              <AlertTitle>{t("trial.verifyTitle")}</AlertTitle>
              <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <span>{t("trial.verifyBody")}</span>
                <Button size="sm" variant="outline" onClick={resendVerification} disabled={resent}>
                  {resent ? t("trial.resent") : t("trial.resend")}
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}
          {!useTrialBanner && trialOnlyStandard && !inReview ? (
            <Alert variant="info">
              <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <span>{t("trial.onlyTier", { tier: titleCase(trialOnlyStandard) })}</span>
                {audienceCount <= 1 ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => switchTier(trialOnlyStandard)}
                    loading={switching === trialOnlyStandard}
                  >
                    {t("trial.switchTo", { tier: titleCase(trialOnlyStandard) })}
                  </Button>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}

          {!useTrialBanner && !inReview ? (
            <section aria-labelledby="tiers">
              <h2 id="tiers" className="mb-3 text-lg font-semibold">
                {t("tiers.title")}
              </h2>
              <div className="grid gap-3 md:grid-cols-3">
                {sortedTiers.map((tier) => {
                  const meta = tiersInfo.data?.find((x) => x.code === tier.code);
                  const tooFewAudiences = !!meta && meta.max_audiences < audienceCount;
                  return (
                    <button
                      key={tier.code}
                      type="button"
                      onClick={() => switchTier(tier.code)}
                      disabled={tooFewAudiences || switching !== null}
                      aria-pressed={tier.selected}
                      className={cn(
                        "relative rounded-lg border p-4 text-left transition-colors touch-target disabled:cursor-not-allowed disabled:opacity-60",
                        tier.selected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
                      )}
                    >
                      {tier.code === "standard" ? (
                        <Badge className="absolute -top-2.5 left-3">{t("tiers.recommended")}</Badge>
                      ) : null}
                      <p className="font-medium">{tier.name}</p>
                      <p className="mt-1 text-xl font-semibold">
                        <Money display={tier.display} local={tier.local} />
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {tier.extra_platforms > 0
                          ? t("tiers.includesExtra", {
                              count: tier.extra_platforms,
                              price: `$${(tier.extra_platform_usd_minor / 100).toFixed(0)}`,
                            })
                          : t("tiers.firstIncluded")}
                      </p>
                      {meta ? (
                        <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                          <li>{t("tiers.runs", { count: meta.runs_target })}</li>
                          <li>{t("tiers.scenarios", { count: meta.scenarios })}</li>
                          <li>{t("tiers.audiences", { count: meta.max_audiences })}</li>
                        </ul>
                      ) : null}
                      {tooFewAudiences ? (
                        <p className="mt-2 text-xs text-warning">{t("tiers.tooFewAudiences")}</p>
                      ) : null}
                      {switching === tier.code ? (
                        <Loader2 className="absolute right-3 top-3 h-4 w-4 animate-spin" aria-hidden />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}

          {!useTrialBanner ? (
            <Tabs defaultValue={defaultTab}>
              {!inReview ? (
                <TabsList>
                  {cardTabAllowed ? (
                    <TabsTrigger value="card">
                      <CreditCard className="h-4 w-4" aria-hidden /> {t("methods.card")}
                    </TabsTrigger>
                  ) : null}
                  {manualTabAllowed ? (
                    <TabsTrigger value="manual">
                      <Landmark className="h-4 w-4" aria-hidden /> {t("methods.manual")}
                    </TabsTrigger>
                  ) : null}
                </TabsList>
              ) : null}
              {cardTabAllowed && !inReview ? (
                <TabsContent value="card">
                  <Card>
                    <CardHeader>
                      <CardTitle>{t("card.title")}</CardTitle>
                      <CardDescription>{t("card.body")}</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-2xl font-semibold">
                        <Money display={info.total_display} local={info.local} />
                      </p>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button asChild variant="outline" size="lg">
                          <Link href={`/tests/${id}/confirm`}>{t("summary.review")}</Link>
                        </Button>
                        <Button size="lg" onClick={payCard} loading={m.payCard.isPending}>
                          <CreditCard aria-hidden /> {t("card.pay")}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              ) : null}
              {manualTabAllowed || inReview ? (
                <TabsContent value="manual">
                  {inReview || pendingManual ? (
                    <ManualOrderDetails order={manual} fallbackPayment={pendingManual} />
                  ) : (
                    <Card>
                      <CardHeader>
                        <CardTitle>{t("manual.title")}</CardTitle>
                        <CardDescription>{t("manual.body")}</CardDescription>
                      </CardHeader>
                      <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-2xl font-semibold">
                          <Money display={info.total_display} local={info.local} />
                        </p>
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          <Button asChild variant="outline" size="lg">
                            <Link href={`/tests/${id}/confirm`}>{t("summary.review")}</Link>
                          </Button>
                          <Button size="lg" onClick={payManual} loading={m.payManual.isPending}>
                            <Landmark aria-hidden /> {t("manual.pay")}
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>
              ) : null}
            </Tabs>
          ) : null}
          <InlineError error={error} />
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardHeader>
              <CardTitle>{t("summary.title")}</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{t("summary.ad")}</dt>
                  <dd className="truncate text-right font-medium">{td.title}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{t("summary.tier")}</dt>
                  <dd className="font-medium">{selectedTier?.name ?? titleCase(info.selected_tier)}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{t("summary.platforms")}</dt>
                  <dd className="text-right">{info.platforms.map(titleCase).join(", ")}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">{t("summary.method")}</dt>
                  <dd>
                    {useTrialBanner
                      ? t("methods.trial")
                      : inReview
                        ? t("methods.manual")
                        : info.methods
                            .filter((x) => x !== "trial")
                            .map((x) => t(`methods.${x}` as never))
                            .join(" / ")}
                  </dd>
                </div>
                <div className="flex justify-between gap-3 border-t border-border pt-2 text-base">
                  <dt className="font-medium">{t("summary.total")}</dt>
                  <dd className="font-semibold">
                    {useTrialBanner ? (
                      t("summary.free")
                    ) : (
                      <Money display={info.total_display} local={info.local} />
                    )}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <CheckoutInner />
    </Suspense>
  );
}