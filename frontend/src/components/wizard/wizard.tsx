"use client";

/**
 * Test wizard: 0 Preset → 1 Ad → 2 Audience → 3 Platforms & schedule → 4 Preview → Confirm.
 * "Draft-then-create": steps 0–2 live in localStorage until the country is known, then the
 * server draft is created (POST /tests), the queued media uploaded and every later step PUT.
 */
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Check, Save } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { ErrorState, InlineError } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { StatusBadge } from "@/components/layout/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { useRouter } from "@/i18n/navigation";
import { upload } from "@/lib/api";
import { isAppError } from "@/lib/errors";
import { EditableTitle } from "@/components/tests/editable-title";
import { minorUnits } from "@/lib/format";
import { useCountries, useTest, useTestMutations } from "@/lib/queries";
import {
  adStepSchema,
  audienceStepSchema,
  platformsStepSchema,
  type AdStepValues,
  type AudienceStepValues,
  type PlatformsStepValues,
} from "@/lib/schemas";
import type { AssetOut, AudienceIn, TestOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  clearDraft,
  defaultAd,
  defaultAudience,
  emptyDraft,
  loadDraft,
  saveDraft,
  type ProfileChoice,
  type WizardDraft,
} from "@/lib/wizard-draft";
import { StepAd } from "./step-ad";
import { StepAudience } from "./step-audience";
import { StepPlatforms } from "./step-platforms";
import { StepPreset } from "./step-preset";
import { StepPreview } from "./step-preview";
import type { QueuedFile } from "./upload-dropzone";

const STEP_KEYS = ["preset", "ad", "audience", "platforms", "preview"] as const;

function audienceValuesFromTest(test: TestOut): AudienceStepValues["audiences"] {
  const list = (test.audiences ?? []) as AudienceIn[];
  if (list.length === 0) return [defaultAudience()];
  return list.map((a) => ({
    name: a.name ?? "Main audience",
    kind: (a.kind as "targeted" | "followers" | "custom") ?? "targeted",
    targeting: {
      age_min: a.targeting?.age_min ?? 18,
      age_max: a.targeting?.age_max ?? 55,
      genders: a.targeting?.genders ?? ["f", "m", "other"],
      interests: a.targeting?.interests ?? [],
      location: a.targeting?.location ?? "",
      radius_km: a.targeting?.radius_km ?? null,
      languages: a.targeting?.languages ?? [],
      audience_size: a.targeting?.audience_size ?? null,
    },
  }));
}

function platformsValuesFromTest(test: TestOut, currency: string): PlatformsStepValues {
  const sched = (test.schedule ?? {}) as {
    start_date?: string | null;
    days?: number;
    post_at?: string | null;
    observe_days?: number;
  };
  return {
    post_type: test.post_type,
    goal: test.goal,
    platforms: test.platforms.map((p) => ({
      code: p.code,
      placements: p.placements,
      budget_share: p.budget_share,
    })),
    budget: test.budget_minor !== null ? test.budget_minor / minorUnits(test.currency || currency) : null,
    // the server draft carries "USD" until post settings are saved; prefer the country's currency before that
    currency: test.budget_minor !== null && test.currency ? test.currency : currency,
    start_date: sched.start_date ?? "",
    days: sched.days ?? 3,
    post_at: sched.post_at ? sched.post_at.slice(0, 16) : "",
    observe_days: sched.observe_days ?? 3,
    tier_code: test.tier_code,
  };
}

export function Wizard() {
  const t = useTranslations("wizard");
  const router = useRouter();
  const params = useSearchParams();
  const { toast } = useToast();
  const countries = useCountries();

  const [draft, setDraft] = useState<WizardDraft | null>(null);
  const [step, setStep] = useState(0);
  const [testId, setTestId] = useState<string | null>(null);
  const [queued, setQueued] = useState<QueuedFile[]>([]);
  const [profileChoice, setProfileChoice] = useState<ProfileChoice | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const seededFromTest = useRef<string | null>(null);

  const test = useTest(testId);
  const m = useTestMutations(testId ?? undefined);

  const adForm = useForm<AdStepValues>({ resolver: zodResolver(adStepSchema), defaultValues: defaultAd() });
  const titleValue = adForm.watch("title") ?? "";

  const audienceForm = useForm<AudienceStepValues>({
    resolver: zodResolver(audienceStepSchema),
    defaultValues: { country_code: "", audiences: [defaultAudience()] },
  });
  const platformsForm = useForm<PlatformsStepValues>({
    resolver: zodResolver(platformsStepSchema),
    defaultValues: {
      post_type: "paid",
      goal: "sales",
      platforms: [],
      budget: null,
      currency: "USD",
      start_date: "",
      days: 3,
      post_at: "",
      observe_days: 3,
      tier_code: "standard",
    },
  });

  // ---- bootstrap from URL / local draft
  useEffect(() => {
    const urlId = params.get("id");
    const urlStep = params.get("step");
    const stored = loadDraft() ?? emptyDraft();
    const id = urlId ?? stored.test_id;
    setDraft(stored);
    setTestId(id);
    if (!id) {
      if (stored.profile) setProfileChoice(stored.profile);
      if (stored.ad) adForm.reset(stored.ad);
      if (stored.country_code || stored.audiences)
        audienceForm.reset({
          country_code: stored.country_code ?? "",
          audiences: stored.audiences ?? [defaultAudience()],
        });
      platformsForm.setValue("tier_code", stored.tier_code);
    }
    const s = urlStep !== null ? Number(urlStep) : id ? Math.max(stored.step, 0) : stored.step;
    setStep(Number.isFinite(s) ? Math.min(Math.max(s, 0), 4) : 0);
    const created = params.get("profile");
    if (created && !id) setProfileChoice({ profile_id: created, mode: "preset", changes: {} });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- run once on mount

  // ---- seed forms from the server draft
  const countryCurrency = useCallback(
    (code: string) => (countries.data ?? []).find((c) => c.code === code)?.currency ?? "USD",
    [countries.data],
  );
  useEffect(() => {
    if (!test.data || seededFromTest.current === test.data.id) return;
    seededFromTest.current = test.data.id;
    const td = test.data;
    const copy = td.ad_copy as {
      caption?: string;
      headline?: string;
      cta?: string;
      link_url?: string | null;
    };
    adForm.reset({
      title: td.title,
      caption: copy.caption ?? "",
      headline: copy.headline ?? "",
      cta: copy.cta ?? "learn_more",
      link_url: copy.link_url ?? "",
    });
    audienceForm.reset({ country_code: td.country_code, audiences: audienceValuesFromTest(td) });
    platformsForm.reset(platformsValuesFromTest(td, countryCurrency(td.country_code)));
    if (td.profile.profile_id)
      setProfileChoice({
        profile_id: td.profile.profile_id,
        mode: td.profile.mode === "one_time" ? "one_time" : "preset",
        changes: {},
      });
  }, [test.data, adForm, audienceForm, platformsForm, countryCurrency]);

  const persistDraft = useCallback(
    (patch: Partial<WizardDraft>) => {
      const next: WizardDraft = { ...(draft ?? emptyDraft()), ...patch };
      setDraft(next);
      saveDraft(next);
    },
    [draft],
  );

  const goTo = useCallback(
    (s: number, id: string | null = testId) => {
      setStep(s);
      setError(null);
      const q = new URLSearchParams();
      if (id) q.set("id", id);
      q.set("step", String(s));
      router.replace(`/tests/new?${q.toString()}`);
      persistDraft({ step: s, test_id: id });
    },
    [router, testId, persistDraft],
  );

  const returnTo = `/tests/new?${testId ? `id=${testId}&` : ""}step=0`;
  const editable = !test.data || test.data.status === "draft" || test.data.status === "awaiting_payment";

  // ---- step 0: preset
  const saveProfileToTest = async (id: string, choice: ProfileChoice) => {
    const out = await m.setProfile.mutateAsync({
      testId: id,
      body: {
        profile_id: choice.profile_id,
        mode: choice.mode,
        changes: choice.changes,
        new_preset_name: choice.new_preset_name ?? null,
      },
    });
    setProfileChoice({
      profile_id: out.profile_id ?? choice.profile_id,
      mode: out.mode === "one_time" ? "one_time" : "preset",
      changes: out.mode === "one_time" ? choice.changes : {},
    });
  };
  const onEditSave = async (choice: ProfileChoice) => {
    setError(null);
    try {
      if (testId) await saveProfileToTest(testId, choice);
      else {
        setProfileChoice(choice);
        persistDraft({ profile: choice });
      }
      toast({ title: t("preset.saved"), variant: "success" });
    } catch (e) {
      setError(e);
      throw e;
    }
  };

  // ---- media helpers
  const uploadQueued = async (id: string) => {
    let i = 0;
    for (const q of queued) {
      i += 1;
      setBusy(t("creating.uploading", { n: i, total: queued.length }));
      await upload<AssetOut>(`/tests/${id}/assets`, q.file);
      URL.revokeObjectURL(q.previewUrl);
    }
    setQueued([]);
  };

  const onDeleteAsset = async (assetId: string) => {
    if (!testId) return;
    await m.deleteAsset.mutateAsync({ testId, assetId });
  };

  // ---- Next handlers
  const next = async () => {
    setError(null);
    setMediaError(null);
    try {
      if (step === 0) {
        if (!profileChoice) {
          setError(new Error(t("preset.required")));
          return;
        }
        if (testId) await saveProfileToTest(testId, profileChoice);
        else persistDraft({ profile: profileChoice });
        goTo(1);
      } else if (step === 1) {
        const ok = await adForm.trigger();
        const values = adForm.getValues();
        const mediaCount = (test.data?.assets.length ?? 0) + queued.length;
        if (mediaCount === 0) setMediaError(t("ad.mediaRequired"));
        if (!ok || mediaCount === 0) return;
        if (testId) {
          await m.update.mutateAsync({
            testId,
            body: {
              title: values.title,
              ad_copy: {
                caption: values.caption,
                headline: values.headline,
                cta: values.cta,
                link_url: values.link_url || null,
              },
            },
          });
        } else persistDraft({ ad: values });
        goTo(2);
      } else if (step === 2) {
        const ok = await audienceForm.trigger();
        if (!ok) return;
        const values = audienceForm.getValues();
        const tier = values.audiences.length > 1 ? "full" : (draft?.tier_code ?? "standard");
        if (testId) {
          await m.update.mutateAsync({
            testId,
            body: {
              audiences: values.audiences,
              tier_code: values.audiences.length > 1 && test.data?.tier_code !== "full" ? "full" : null,
            },
          });
          goTo(3);
        } else {
          setBusy(t("creating.test"));
          const ad = adForm.getValues();
          const created = await m.create.mutateAsync({
            title: ad.title,
            country_code: values.country_code,
            tier_code: tier,
            ad_copy: {
              caption: ad.caption,
              headline: ad.headline,
              cta: ad.cta,
              link_url: ad.link_url || null,
            },
            audiences: values.audiences,
          });
          if (profileChoice) {
            setBusy(t("creating.profile"));
            await saveProfileToTest(created.id, profileChoice);
          }
          await uploadQueued(created.id);
          setBusy(null);
          setTestId(created.id);
          seededFromTest.current = null;
          persistDraft({ test_id: created.id, profile: null, ad: null, audiences: null, country_code: null });
          platformsForm.setValue("currency", countryCurrency(values.country_code));
          platformsForm.setValue("tier_code", tier);
          goTo(3, created.id);
        }
      } else if (step === 3) {
        if (!testId) return;
        const ok = await platformsForm.trigger();
        if (!ok) return;
        const v = platformsForm.getValues();
        if (test.data && test.data.tier_code !== v.tier_code)
          await m.update.mutateAsync({ testId, body: { tier_code: v.tier_code } });
        await m.setPlatforms.mutateAsync({
          testId,
          body: v.platforms.map((p) => ({
            code: p.code,
            placements: p.placements,
            budget_share: v.platforms.length === 1 ? 100 : p.budget_share,
          })),
        });
        await m.setPost.mutateAsync({
          testId,
          body: {
            post_type: v.post_type,
            goal: v.goal,
            budget_minor:
              v.post_type === "organic" || v.budget === null
                ? null
                : Math.round(v.budget * minorUnits(v.currency)),
            currency: v.currency,
            schedule:
              v.post_type === "organic"
                ? {
                    post_at: v.post_at ? new Date(v.post_at).toISOString() : null,
                    observe_days: v.observe_days,
                    days: v.days,
                  }
                : { start_date: v.start_date || null, days: v.days, observe_days: v.observe_days },
          },
        });
        goTo(4);
      } else if (step === 4 && testId) {
        clearDraft();
        router.push(`/tests/${testId}/confirm`);
      }
    } catch (e) {
      setBusy(null);
      if (isAppError(e) && e.code === "profile_invalid") {
        setError(new Error(t("preset.invalid", { fields: Object.keys(e.fieldErrors).join(", ") })));
        return;
      }
      setError(e);
    }
  };

  const saveAndExit = async () => {
    if (step <= 2 && !testId) {
      if (step === 0 && profileChoice) persistDraft({ profile: profileChoice });
      if (step === 1) persistDraft({ ad: adForm.getValues() });
      if (step === 2)
        persistDraft({
          country_code: audienceForm.getValues("country_code") || null,
          audiences: audienceForm.getValues("audiences"),
        });
      toast({ title: t("draftSavedLocally") });
    }
    router.push(testId ? `/tests/${testId}` : "/dashboard");
  };

  const currency = platformsForm.watch("currency");
  const audienceCount = audienceForm.watch("audiences").length;
  const countryCode = audienceForm.watch("country_code");
  const canJump = (s: number) => (testId ? s <= 4 : s <= step);
  const stepsDone = useMemo(
    () =>
      testId
        ? [0, 1, 2, ...(test.data?.platforms.length ? [3] : [])]
        : Array.from({ length: step }, (_x, i) => i),
    [testId, test.data, step],
  );

  if (testId && test.isLoading) return <PageSkeleton />;
  if (testId && test.isError) return <ErrorState error={test.error} onRetry={() => test.refetch()} />;
  if (test.data && !editable) {
    return (
      <Alert variant="warning">
        <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("notEditable")}</span>
          <Button variant="outline" size="sm" onClick={() => router.push(`/tests/${test.data?.id}`)}>
            {t("openTest")}
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    // -my-6 cancels the app shell's own `py-6` on <main> so this component can own the full
    // viewport height below the 3.5rem (h-14) navbar itself, with pt-6/pb-6 added back below to
    // restore the same visual spacing. Only the step-content column scrolls (overflow-y-auto);
    // the page around it (header, step nav, action bar) never scrolls, so the bottom bar can't
    // leave trailing blank space below it the way `sticky` did.
    <div className="mx-auto -my-6 flex h-[calc(100dvh-3.5rem)] max-w-6xl flex-col">
      <div className="shrink-0 pt-6">
        {/* <PageHeader
          title={test.data ? t("editTitle", { title: test.data.title }) : t("title")}
          actions={test.data ? <StatusBadge status={test.data.status} /> : null}
        /> */}
        <PageHeader
          title={
            <EditableTitle
              value={titleValue}
              placeholder={t("title")}         
              onSave={async (next) => {
                if (testId) {
                  await m.update.mutateAsync({ testId, body: { title: next } });
                  adForm.setValue("title", next, { shouldDirty: true, shouldValidate: true });
                } else {
                  adForm.setValue("title", next, { shouldDirty: true, shouldValidate: true });
                  persistDraft({ ad: adForm.getValues() });
                }
              }}
            />
          }
          actions={test.data ? <StatusBadge status={test.data.status} /> : null}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-6 sm:flex-row sm:items-stretch">
        {/* Step list: horizontal scroller on mobile, vertical sidebar from sm: up. It's a normal
            (non-scrolling) sibling of the content column, so it never moves — only the content
            column below scrolls. */}
        <nav aria-label={t("stepsLabel")} className="shrink-0 sm:w-56">
          <ol className="flex gap-1 overflow-x-auto pb-1 sm:flex-col sm:gap-0 sm:overflow-visible sm:pb-0">
            {STEP_KEYS.map((k, i) => {
              const active = i === step;
              const done = stepsDone.includes(i) && !active;
              const isLast = i === STEP_KEYS.length - 1;
              return (
                <li key={k} className="relative shrink-0 sm:shrink sm:pb-6 sm:last:pb-0">
                  {!isLast ? (
                    <span
                      aria-hidden
                      className={cn(
                        "absolute left-4 top-8 hidden w-0.5 -translate-x-1/2 sm:bottom-0 sm:block",
                        i < step ? "bg-success" : "bg-border",
                      )}
                    />
                  ) : null}
                  <button
                    type="button"
                    onClick={() => canJump(i) && goTo(i)}
                    disabled={!canJump(i)}
                    aria-current={active ? "step" : undefined}
                    className="relative z-10 flex flex-col items-center gap-1 text-center touch-target disabled:cursor-not-allowed sm:w-full sm:flex-row sm:items-start sm:gap-3 sm:text-left"
                  >
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-medium tabular",
                        active
                          ? "border-primary bg-primary text-primary-foreground"
                          : done
                            ? "border-success bg-success text-white"
                            : "border-border bg-background text-muted-foreground",
                      )}
                    >
                      {done ? <Check className="h-4 w-4" aria-hidden /> : i}
                    </span>
                    <span className="flex flex-col sm:pt-1">
                      <span
                        className={cn(
                          "max-w-[5rem] text-[11px] font-medium leading-tight sm:max-w-none sm:text-sm",
                          active ? "text-primary" : done ? "text-foreground" : "text-muted-foreground",
                        )}
                      >
                        {t(`steps.${k}.title`)}
                      </span>
                      <span className="hidden text-[10px] text-muted-foreground sm:block">
                        {t(`steps.${k}.subtitle`)}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto pr-1">
        <div className="space-y-4 pb-4">
        {step === 0 ? (
          <StepPreset
            value={profileChoice}
            onChange={(c) => setProfileChoice(c)}
            onEditSave={onEditSave}
            saving={m.setProfile.isPending}
            returnTo={returnTo}
            preselectId={params.get("profile")}
          />
        ) : null}
        {step === 1 ? (
          <StepAd
            form={adForm}
            testId={testId}
            assets={test.data?.assets ?? []}
            queued={queued}
            onQueuedChange={(u) => setQueued(u)}
            onUploaded={() => m.invalidate()}
            onDeleteAsset={onDeleteAsset}
            mediaError={mediaError}
          />
        ) : null}
        {step === 2 ? <StepAudience form={audienceForm} countryLocked={!!testId} /> : null}
        {step === 3 && testId ? (
          <StepPlatforms
            form={platformsForm}
            currency={currency}
            countryCode={countryCode}
            audienceCount={audienceCount}
          />
        ) : null}
        {step === 4 && test.data ? <StepPreview test={test.data} /> : null}
        {busy ? (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {busy}
          </p>
        ) : null}
        <InlineError error={error} />
        </div>
        </div>
      </div>

      {/* Persistent action bar: a normal (non-scrolling) flex item pinned to the bottom of this
          fixed-height page, so Back/Save & exit/Next are always visible with no page scroll and
          no leftover blank space below them. */}
      <div className="shrink-0 flex flex-col-reverse gap-2 border-t border-border bg-background pb-6 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => step > 0 && goTo(step - 1)}
            disabled={step === 0}
          >
            <ArrowLeft aria-hidden /> {t("back")}
          </Button>
          <Button type="button" variant="outline" onClick={saveAndExit}>
            <Save aria-hidden /> {t("saveExit")}
          </Button>
        </div>
        <Button
          type="button"
          onClick={next}
          disabled={step === 0 && !profileChoice}
          loading={
            busy !== null ||
            m.update.isPending ||
            m.setProfile.isPending ||
            m.setPlatforms.isPending ||
            m.setPost.isPending ||
            m.create.isPending
          }
        >
          {step === 4 ? t("looksGood") : t("next")} <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  );
}