"use client";

import { useTranslations } from "next-intl";
import { useEffect, useMemo } from "react";
import { Controller, type UseFormReturn } from "react-hook-form";
import { FormField } from "@/components/layout/form-field";
import { Money } from "@/components/layout/money";
import { PlatformStatusBadge } from "@/components/layout/status-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { formatMoney, titleCase } from "@/lib/format";
import { usePlatforms, useTiers } from "@/lib/queries";
import type { PlatformsStepValues } from "@/lib/schemas";
import { GOALS, POST_TYPES, type PlatformOut } from "@/lib/types";
import { cn } from "@/lib/utils";

function ChoiceCard({
  selected,
  onClick,
  title,
  body,
  disabled,
  badge,
}: {
  selected: boolean;
  onClick: () => void;
  title: string;
  body?: string;
  disabled?: boolean;
  badge?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={cn(
        "rounded-lg border p-3 text-left transition-colors touch-target disabled:cursor-not-allowed disabled:opacity-50",
        selected ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
      )}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">{title}</span>
        {badge}
      </div>
      {body ? <p className="mt-1 text-xs text-muted-foreground">{body}</p> : null}
    </button>
  );
}

/** Evenly split percentage shares that sum to 100 (remainder on the first). */
export function evenShares(n: number): number[] {
  if (n <= 0) return [];
  const base = Math.floor(100 / n);
  const shares = Array.from({ length: n }, () => base);
  shares[0] += 100 - base * n;
  return shares;
}

export function StepPlatforms({
  form,
  currency,
  countryCode,
  audienceCount,
}: {
  form: UseFormReturn<PlatformsStepValues>;
  currency: string;
  countryCode: string;
  audienceCount: number;
}) {
  const t = useTranslations("wizard.platforms");
  const platforms = usePlatforms();
  const postType = form.watch("post_type");
  const goal = form.watch("goal");
  const selected = form.watch("platforms");
  const tierCode = form.watch("tier_code");
  const tiers = useTiers(countryCode, Math.max(1, selected.length));
  const e = form.formState.errors;

  const available = useMemo(
    () => (platforms.data ?? []).filter((p) => p.status !== "planned"),
    [platforms.data],
  );
  const byCode = useMemo(
    () => Object.fromEntries((platforms.data ?? []).map((p) => [p.code, p])) as Record<string, PlatformOut>,
    [platforms.data],
  );

  /** Goals supported by every selected platform for the chosen post type. */
  const supportedGoals = useMemo(() => {
    if (selected.length === 0) return GOALS;
    return GOALS.filter((g) =>
      selected.every((s) => {
        const p = byCode[s.code];
        if (!p) return true;
        const pt = p.post_types.find((x) => x.post_type === postType);
        return pt ? pt.supported_goals.includes(g) : (p.supported_goals[postType] ?? []).includes(g);
      }),
    );
  }, [selected, byCode, postType]);

  useEffect(() => {
    if (!supportedGoals.includes(goal) && supportedGoals.length > 0)
      form.setValue("goal", supportedGoals[0], { shouldValidate: true });
  }, [supportedGoals, goal, form]);

  useEffect(() => {
    // more than one audience requires the Full tier (backend confirm rule)
    if (audienceCount > 1 && tierCode !== "full") form.setValue("tier_code", "full");
  }, [audienceCount, tierCode, form]);

  const togglePlatform = (p: PlatformOut) => {
    const idx = selected.findIndex((s) => s.code === p.code);
    let next =
      idx >= 0
        ? selected.filter((s) => s.code !== p.code)
        : [
            ...selected,
            { code: p.code, placements: p.placements.slice(0, 1).map((x) => x.code), budget_share: 0 },
          ];
    if (next.length > 3) return;
    const shares = evenShares(next.length);
    next = next.map((s, i) => ({ ...s, budget_share: shares[i] }));
    form.setValue("platforms", next, { shouldValidate: true });
  };

  const setPlacement = (code: string, placement: string, on: boolean) => {
    form.setValue(
      "platforms",
      selected.map((s) =>
        s.code === code
          ? {
              ...s,
              placements: on ? [...s.placements, placement] : s.placements.filter((x) => x !== placement),
            }
          : s,
      ),
      { shouldValidate: true },
    );
  };

  /** Shares are whole percentages that always add up to 100. */
  const setShare = (index: number, value: number) => {
    if (selected.length === 2) {
      form.setValue(
        "platforms",
        selected.map((s, i) => ({ ...s, budget_share: i === index ? value : 100 - value })),
        { shouldValidate: true },
      );
      return;
    }
    // 3 platforms: adjust this one, scale the others to keep the total at 100
    const rest = selected.filter((_s, i) => i !== index);
    const restTotal = rest.reduce((a, s) => a + s.budget_share, 0) || 1;
    const remaining = Math.max(0, 100 - value);
    let acc = 0;
    const next = selected.map((s, i) => {
      if (i === index) return { ...s, budget_share: value };
      const share = Math.round((s.budget_share / restTotal) * remaining);
      acc += share;
      return { ...s, budget_share: share };
    });
    const drift = 100 - value - acc;
    const lastOther = next
      .map((_s, i) => i)
      .filter((i) => i !== index)
      .pop();
    if (lastOther !== undefined)
      next[lastOther] = {
        ...next[lastOther],
        budget_share: Math.max(0, next[lastOther].budget_share + drift),
      };
    form.setValue("platforms", next, { shouldValidate: true });
  };

  const tier = tiers.data?.find((x) => x.code === tierCode);
  const total = selected.reduce((a, s) => a + s.budget_share, 0);
  const platformsError = (e.platforms as { message?: string } | undefined)?.message;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("postTypeTitle")}</CardTitle>
          <CardDescription>{t("postTypeBody")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          {POST_TYPES.map((pt) => (
            <ChoiceCard
              key={pt}
              selected={postType === pt}
              onClick={() => form.setValue("post_type", pt, { shouldValidate: true })}
              title={t(`postTypes.${pt}.title`)}
              body={t(`postTypes.${pt}.body`)}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("platformsTitle")}</CardTitle>
          <CardDescription>{t("platformsBody")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {available.map((p) => {
              const on = selected.some((s) => s.code === p.code);
              const supportsType =
                p.post_types.some((x) => x.post_type === postType) || Boolean(p.supported_goals[postType]);
              return (
                <ChoiceCard
                  key={p.code}
                  selected={on}
                  disabled={!supportsType}
                  onClick={() => togglePlatform(p)}
                  title={p.name}
                  body={
                    supportsType ? t("placementsCount", { count: p.placements.length }) : t("notForPostType")
                  }
                  badge={<PlatformStatusBadge status={p.status} />}
                />
              );
            })}
          </div>
          {platformsError ? (
            <p role="alert" className="text-sm text-danger">
              {t(`errors.${platformsError}` as never)}
            </p>
          ) : null}
          {selected.map((s, i) => {
            const p = byCode[s.code];
            if (!p) return null;
            const perr = (e.platforms as Record<number, { placements?: { message?: string } }> | undefined)?.[
              i
            ]?.placements?.message;
            return (
              <div key={s.code} className="rounded-lg border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-medium">{p.name}</p>
                  {selected.length > 1 ? (
                    <span className="text-sm tabular text-muted-foreground">
                      {Math.round(s.budget_share)}%
                    </span>
                  ) : null}
                </div>
                <div
                  role="group"
                  aria-label={t("placementsFor", { platform: p.name })}
                  className="flex flex-wrap gap-2"
                >
                  {p.placements.map((pl) => {
                    const checked = s.placements.includes(pl.code);
                    return (
                      <label
                        key={pl.code}
                        className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm touch-target ${checked ? "border-primary bg-primary/5" : "border-border"}`}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(c) => setPlacement(s.code, pl.code, c === true)}
                        />
                        {titleCase(pl.code)}
                        <span className="text-xs text-muted-foreground">{pl.ratios.join(" · ")}</span>
                      </label>
                    );
                  })}
                </div>
                {perr ? (
                  <p role="alert" className="mt-1 text-sm text-danger">
                    {t("errors.placement_required")}
                  </p>
                ) : null}
                {selected.length > 1 && postType !== "organic" ? (
                  <div className="mt-3">
                    <Slider
                      aria-label={t("shareFor", { platform: p.name })}
                      value={[Math.round(s.budget_share)]}
                      min={0}
                      max={100}
                      step={5}
                      onValueChange={([v]) => setShare(i, v)}
                    />
                  </div>
                ) : null}
              </div>
            );
          })}
          {selected.length > 1 && postType !== "organic" ? (
            <p
              className={cn(
                "text-xs",
                Math.abs(total - 100) > 0.011 ? "text-danger" : "text-muted-foreground",
              )}
            >
              {t("sharesTotal", { total: Math.round(total) })}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("goalTitle")}</CardTitle>
          <CardDescription>{t("goalBody")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {GOALS.map((g) => (
            <ChoiceCard
              key={g}
              selected={goal === g}
              disabled={!supportedGoals.includes(g)}
              onClick={() => form.setValue("goal", g, { shouldValidate: true })}
              title={t(`goals.${g}.title`)}
              body={supportedGoals.includes(g) ? t(`goals.${g}.body`) : t("goalNotSupported")}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{postType === "organic" ? t("organicScheduleTitle") : t("scheduleTitle")}</CardTitle>
          <CardDescription>
            {postType === "organic" ? t("organicScheduleBody") : t("scheduleBody")}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {postType === "organic" ? (
            <>
              <FormField id="post_at" label={t("fields.postAt")} error={e.post_at} required>
                <Input
                  id="post_at"
                  type="datetime-local"
                  aria-invalid={!!e.post_at}
                  {...form.register("post_at")}
                />
              </FormField>
              <FormField
                id="observe_days"
                label={t("fields.observeDays")}
                error={e.observe_days}
                help={t("fields.observeDaysHelp")}
              >
                <Input
                  id="observe_days"
                  type="number"
                  min={1}
                  max={7}
                  inputMode="numeric"
                  {...form.register("observe_days", { valueAsNumber: true })}
                />
              </FormField>
            </>
          ) : (
            <>
              <FormField id="start_date" label={t("fields.startDate")} error={e.start_date} required>
                <Input
                  id="start_date"
                  type="date"
                  min={new Date().toISOString().slice(0, 10)}
                  aria-invalid={!!e.start_date}
                  {...form.register("start_date")}
                />
              </FormField>
              <FormField id="days" label={t("fields.days")} error={e.days} help={t("fields.daysHelp")}>
                <Input
                  id="days"
                  type="number"
                  min={1}
                  max={14}
                  inputMode="numeric"
                  {...form.register("days", { valueAsNumber: true })}
                />
              </FormField>
              <FormField
                id="budget"
                label={t("fields.budget", { currency })}
                error={e.budget}
                required
                help={t("fields.budgetHelp")}
              >
                <Controller
                  control={form.control}
                  name="budget"
                  render={({ field }) => (
                    <Input
                      id="budget"
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="any"
                      value={field.value ?? ""}
                      aria-invalid={!!e.budget}
                      onChange={(ev) =>
                        field.onChange(ev.target.value === "" ? null : Number(ev.target.value))
                      }
                    />
                  )}
                />
              </FormField>
            </>
          )}
        </CardContent>
      </Card>

      <Alert variant="info">
        <AlertDescription className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <span>
            {t("priceLine", {
              tier: tier?.name ?? titleCase(tierCode),
              platforms: Math.max(1, selected.length),
            })}
            {tier && tier.extra_platform_usd_minor > 0
              ? ` · ${t("extraPlatform", { price: formatMoney(tier.extra_platform_usd_minor, "USD") })}`
              : ""}
          </span>
          {tier ? (
            <strong className="tabular">
              <Money
                usdMinor={
                  tier.price_usd_minor + tier.extra_platform_usd_minor * Math.max(0, selected.length - 1)
                }
                local={
                  tier.local && tier.extra_platform_local
                    ? {
                        ...tier.local,
                        amount_minor:
                          tier.local.amount_minor +
                          tier.extra_platform_local.amount_minor * Math.max(0, selected.length - 1),
                        display: "",
                      }
                    : tier.local
                }
              />
            </strong>
          ) : null}
        </AlertDescription>
      </Alert>
      <p className="text-xs text-muted-foreground">{t("tierNote")}</p>
    </div>
  );
}
