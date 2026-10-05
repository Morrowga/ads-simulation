"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { Controller, useFieldArray, type UseFormReturn } from "react-hook-form";
import { FormField } from "@/components/layout/form-field";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { useCountries } from "@/lib/queries";
import type { AudienceStepValues } from "@/lib/schemas";
import { defaultAudience } from "@/lib/wizard-draft";
import { TagPicker } from "./tag-picker";

const GENDERS = ["f", "m", "other"] as const;
const AUDIENCE_KINDS = ["targeted", "followers", "custom"] as const;

export function StepAudience({
  form,
  countryLocked,
}: {
  form: UseFormReturn<AudienceStepValues>;
  countryLocked: boolean;
}) {
  const t = useTranslations("wizard.audience");
  const countries = useCountries();
  const { fields, append, remove } = useFieldArray({ control: form.control, name: "audiences" });
  const countryCode = form.watch("country_code");
  const country = (countries.data ?? []).find((c) => c.code === countryCode);
  const e = form.formState.errors;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("countryTitle")}</CardTitle>
          <CardDescription>{countryLocked ? t("countryLocked") : t("countryBody")}</CardDescription>
        </CardHeader>
        <CardContent>
          <FormField id="country_code" label={t("fields.country")} error={e.country_code} required>
            <Controller
              control={form.control}
              name="country_code"
              render={({ field }) => (
                <Select
                  value={field.value}
                  disabled={countryLocked}
                  onValueChange={(v) => {
                    field.onChange(v);
                    // default language groups for each audience from the country
                    const c = (countries.data ?? []).find((x) => x.code === v);
                    if (c) {
                      const langs = c.language_groups.map((g) => g.code);
                      form
                        .getValues("audiences")
                        .forEach((_a, i) => form.setValue(`audiences.${i}.targeting.languages`, langs));
                    }
                  }}
                >
                  <SelectTrigger id="country_code" className="sm:w-72" aria-invalid={!!e.country_code}>
                    <SelectValue placeholder={t("fields.countryPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {(countries.data ?? [])
                      .filter((c) => c.active)
                      .map((c) => (
                        <SelectItem key={c.code} value={c.code}>
                          {c.name} · {c.currency}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
        </CardContent>
      </Card>

      {fields.map((f, i) => {
        const ae = e.audiences?.[i];
        const targeting = form.watch(`audiences.${i}.targeting`);
        return (
          <Card key={f.id}>
            <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
              <div>
                <CardTitle>{fields.length > 1 ? t("audienceN", { n: i + 1 }) : t("audienceTitle")}</CardTitle>
                <CardDescription>{t("audienceBody")}</CardDescription>
              </div>
              {fields.length > 1 ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t("removeAudience")}
                  onClick={() => remove(i)}
                >
                  <Trash2 aria-hidden />
                </Button>
              ) : null}
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <FormField id={`aud-${i}-name`} label={t("fields.name")} error={ae?.name} required>
                <Input id={`aud-${i}-name`} maxLength={80} {...form.register(`audiences.${i}.name`)} />
              </FormField>
              <FormField id={`aud-${i}-kind`} label={t("fields.kind")} error={ae?.kind}>
                <Controller
                  control={form.control}
                  name={`audiences.${i}.kind`}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id={`aud-${i}-kind`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {AUDIENCE_KINDS.map((k) => (
                          <SelectItem key={k} value={k}>
                            {t(`kinds.${k}`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </FormField>
              <FormField
                id={`aud-${i}-location`}
                label={t("fields.location")}
                error={ae?.targeting?.location}
                required
              >
                <Input
                  id={`aud-${i}-location`}
                  maxLength={120}
                  placeholder={t("fields.locationHelp")}
                  aria-invalid={!!ae?.targeting?.location}
                  {...form.register(`audiences.${i}.targeting.location`)}
                />
              </FormField>
              <FormField id={`aud-${i}-radius`} label={t("fields.radius")} error={ae?.targeting?.radius_km}>
                <Controller
                  control={form.control}
                  name={`audiences.${i}.targeting.radius_km`}
                  render={({ field }) => (
                    <Input
                      id={`aud-${i}-radius`}
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={500}
                      placeholder={t("fields.radiusHelp")}
                      value={field.value ?? ""}
                      onChange={(ev) =>
                        field.onChange(ev.target.value === "" ? null : Number(ev.target.value))
                      }
                    />
                  )}
                />
              </FormField>
              <FormField
                id={`aud-${i}-age`}
                label={t("fields.age", {
                  min: targeting.age_min,
                  max: targeting.age_max >= 65 ? "65+" : targeting.age_max,
                })}
                error={ae?.targeting?.age_max ?? ae?.targeting?.age_min}
                className="sm:col-span-2"
              >
                <Slider
                  id={`aud-${i}-age`}
                  min={13}
                  max={65}
                  step={1}
                  minStepsBetweenThumbs={1}
                  value={[targeting.age_min, Math.min(targeting.age_max, 65)]}
                  thumbLabels={[t("fields.ageMin"), t("fields.ageMax")]}
                  onValueChange={([lo, hi]) => {
                    form.setValue(`audiences.${i}.targeting.age_min`, lo, { shouldValidate: true });
                    form.setValue(`audiences.${i}.targeting.age_max`, hi >= 65 ? 99 : hi, {
                      shouldValidate: true,
                    });
                  }}
                />
              </FormField>
              <FormField
                id={`aud-${i}-genders`}
                label={t("fields.genders")}
                error={ae?.targeting?.genders?.message ? String(ae.targeting.genders.message) : undefined}
                className="sm:col-span-2"
              >
                <Controller
                  control={form.control}
                  name={`audiences.${i}.targeting.genders`}
                  render={({ field }) => (
                    <div role="group" className="flex flex-wrap gap-2">
                      {GENDERS.map((g) => {
                        const on = field.value.includes(g);
                        return (
                          <label
                            key={g}
                            className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm touch-target ${on ? "border-primary bg-primary/5" : "border-border"}`}
                          >
                            <Checkbox
                              checked={on}
                              onCheckedChange={(c) =>
                                field.onChange(
                                  c ? [...field.value, g] : field.value.filter((x: string) => x !== g),
                                )
                              }
                            />
                            {t(`genders.${g}`)}
                          </label>
                        );
                      })}
                    </div>
                  )}
                />
              </FormField>
              <FormField id={`aud-${i}-languages`} label={t("fields.languages")} className="sm:col-span-2">
                <Controller
                  control={form.control}
                  name={`audiences.${i}.targeting.languages`}
                  render={({ field }) => (
                    <div role="group" className="flex flex-wrap gap-2">
                      {(country?.language_groups ?? []).map((g) => {
                        const on = field.value.includes(g.code);
                        return (
                          <label
                            key={g.code}
                            className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm touch-target ${on ? "border-primary bg-primary/5" : "border-border"}`}
                          >
                            <Checkbox
                              checked={on}
                              onCheckedChange={(c) =>
                                field.onChange(
                                  c
                                    ? [...field.value, g.code]
                                    : field.value.filter((x: string) => x !== g.code),
                                )
                              }
                            />
                            {g.name}
                            <Badge variant="neutral">{Math.round(g.share * 100)}%</Badge>
                          </label>
                        );
                      })}
                      {!country ? (
                        <span className="text-sm text-muted-foreground">{t("pickCountryFirst")}</span>
                      ) : null}
                    </div>
                  )}
                />
              </FormField>
              <FormField id={`aud-${i}-interests`} label={t("fields.interests")} className="sm:col-span-2">
                <Controller
                  control={form.control}
                  name={`audiences.${i}.targeting.interests`}
                  render={({ field }) => (
                    <TagPicker
                      id={`aud-${i}-interests`}
                      value={field.value}
                      onChange={field.onChange}
                      placeholder={t("fields.interestsPlaceholder")}
                    />
                  )}
                />
              </FormField>
              <FormField
                id={`aud-${i}-size`}
                label={t("fields.audienceSize")}
                error={ae?.targeting?.audience_size}
              >
                <Controller
                  control={form.control}
                  name={`audiences.${i}.targeting.audience_size`}
                  render={({ field }) => (
                    <Input
                      id={`aud-${i}-size`}
                      type="number"
                      inputMode="numeric"
                      min={100}
                      step={100}
                      placeholder={t("fields.audienceSizeHelp")}
                      value={field.value ?? ""}
                      onChange={(ev) =>
                        field.onChange(ev.target.value === "" ? null : Number(ev.target.value))
                      }
                    />
                  )}
                />
              </FormField>
            </CardContent>
          </Card>
        );
      })}
      {fields.length < 3 ? (
        <Button
          type="button"
          variant="outline"
          onClick={() =>
            append(
              defaultAudience(
                t("audienceN", { n: fields.length + 1 }),
                country?.language_groups.map((g) => g.code) ?? [],
              ),
            )
          }
        >
          <Plus aria-hidden /> {t("addAudience")}
        </Button>
      ) : null}
      {fields.length > 1 ? (
        <Alert variant="info">
          <AlertDescription>{t("fullTierNote")}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}