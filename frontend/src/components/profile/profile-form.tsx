"use client";

/**
 * Category-driven Business Profile form. Renders the template's questions from
 * GET /categories/{code} grouped into the sections of the frontend document (5.1).
 */
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { FormField } from "@/components/layout/form-field";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { titleCase } from "@/lib/format";
import type { CategoryTemplateOut, QuestionOut } from "@/lib/types";

export type ProfileData = Record<string, unknown>;

type Section = "basics" | "sell" | "customers" | "reputation" | "notes";
const REPUTATION_KEYS = new Set([
  "followers",
  "review_count",
  "rating",
  "months_in_business",
  "page_url",
  "map_url",
  "page_link",
]);
const BASIC_KEYS = new Set([
  "business_name",
  "business_type",
  "location",
  "city",
  "area",
  "opening_hours",
  "brand_name",
]);

export function sectionOf(q: QuestionOut): Section {
  if (REPUTATION_KEYS.has(q.key) || q.feeds_trait === "brand_relationship") return "reputation";
  if (BASIC_KEYS.has(q.key)) return "basics";
  if (q.feeds_trait === "familiarity" || q.feeds_trait === "language_group" || q.key.startsWith("customer"))
    return "customers";
  return "sell";
}

/** Initial values: template defaults applied where the data has no answer. */
export function initialProfileData(
  template: CategoryTemplateOut | undefined,
  data: ProfileData = {},
): ProfileData {
  const out: ProfileData = { ...data };
  for (const q of template?.questions ?? []) {
    if (out[q.key] === undefined || out[q.key] === null) {
      if (q.default !== undefined && q.default !== null) out[q.key] = q.default;
      else if (q.type === "multiselect") out[q.key] = [];
      else if (q.type === "boolean") out[q.key] = false;
      else if (q.type === "sliders")
        out[q.key] = Object.fromEntries((q.options ?? []).map((o) => [String(o), 0.5]));
    }
  }
  return out;
}

/** Client-side required check mirroring the backend rule (defaults satisfy required questions). */
export function missingRequired(template: CategoryTemplateOut | undefined, data: ProfileData): string[] {
  return (template?.questions ?? [])
    .filter((q) => {
      if (!q.required) return false;
      const v = data[q.key];
      const empty = v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);
      return empty && (q.default === undefined || q.default === null);
    })
    .map((q) => q.key);
}

function optionLabel(o: unknown): string {
  if (o && typeof o === "object" && "label" in o) return String((o as { label: unknown }).label);
  return titleCase(String(o));
}
function optionValue(o: unknown): string {
  if (o && typeof o === "object" && "value" in o) return String((o as { value: unknown }).value);
  return String(o);
}

export function ProfileForm({
  template,
  data,
  onChange,
  errors = {},
  disabled = false,
}: {
  template: CategoryTemplateOut;
  data: ProfileData;
  onChange: (next: ProfileData) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}) {
  const t = useTranslations("profiles.form");
  const [notes, setNotes] = useState(String(data.brand_notes ?? ""));
  const set = (key: string, value: unknown) => onChange({ ...data, [key]: value });
  const groups = useMemo(() => {
    const g: Record<Section, QuestionOut[]> = {
      basics: [],
      sell: [],
      customers: [],
      reputation: [],
      notes: [],
    };
    for (const q of template.questions) g[sectionOf(q)].push(q);
    return g;
  }, [template]);

  const renderQuestion = (q: QuestionOut) => {
    const id = `q-${q.key}`;
    const err = errors[q.key];
    const value = data[q.key];
    const help = q.help ?? undefined;
    switch (q.type) {
      case "number":
        return (
          <FormField key={q.key} id={id} label={q.label} error={err} required={q.required}>
            <Input
              id={id}
              type="number"
              inputMode="decimal"
              min={q.min ?? undefined}
              max={q.max ?? undefined}
              step="any"
              placeholder={help}
              value={value === undefined || value === null ? "" : String(value)}
              onChange={(e) => set(q.key, e.target.value === "" ? null : Number(e.target.value))}
              aria-invalid={!!err}
              disabled={disabled}
            />
          </FormField>
        );
      case "select":
        return (
          <FormField key={q.key} id={id} label={q.label} error={err} required={q.required}>
            <Select
              value={value ? String(value) : ""}
              onValueChange={(v) => {
                if (v !== "") set(q.key, v);
              }}
              disabled={disabled}
            >
              <SelectTrigger id={id} aria-invalid={!!err}>
                <SelectValue placeholder={t("choose")} />
              </SelectTrigger>
              <SelectContent>
                {(q.options ?? []).map((o) => (
                  <SelectItem key={optionValue(o)} value={optionValue(o)}>
                    {optionLabel(o)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
        );
      case "multiselect": {
        const selected = Array.isArray(value) ? (value as string[]) : [];
        return (
          <FormField
            key={q.key}
            id={id}
            label={q.label}
            error={err}
            required={q.required}
            className="sm:col-span-2"
          >
            <div id={id} role="group" aria-labelledby={`${id}-label`} className="flex flex-wrap gap-2">
              {(q.options ?? []).map((o) => {
                const v = optionValue(o);
                const on = selected.includes(v);
                return (
                  <label
                    key={v}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm touch-target ${on ? "border-primary bg-primary/5" : "border-border"}`}
                  >
                    <Checkbox
                      checked={on}
                      disabled={disabled}
                      onCheckedChange={(c) =>
                        set(q.key, c ? [...selected, v] : selected.filter((x) => x !== v))
                      }
                    />
                    {optionLabel(o)}
                  </label>
                );
              })}
            </div>
          </FormField>
        );
      }
      case "boolean":
        return (
          <FormField key={q.key} id={id} label={q.label} error={err} required={q.required}>
            <div className="flex items-center gap-3">
              <Switch
                id={id}
                checked={value === true}
                onCheckedChange={(v) => set(q.key, v)}
                disabled={disabled}
              />
              <span className="text-sm text-muted-foreground">{value === true ? t("yes") : t("no")}</span>
            </div>
          </FormField>
        );
      case "sliders": {
        const dims = (q.options ?? []).map(optionValue);
        const obj = (value && typeof value === "object" ? value : {}) as Record<string, number>;
        const min = q.min ?? 0;
        const max = q.max ?? 1;
        return (
          <FormField
            key={q.key}
            id={id}
            label={q.label}
            error={err}
            required={q.required}
            className="sm:col-span-2"
          >
            <div id={id} className="space-y-3 rounded-md border border-border p-3">
              {dims.map((d) => {
                const v = typeof obj[d] === "number" ? obj[d] : (min + max) / 2;
                return (
                  <div key={d} className="grid grid-cols-[1fr_auto] items-center gap-3">
                    <div>
                      <div className="mb-1 flex justify-between text-sm">
                        <span>{titleCase(d)}</span>
                        <span className="tabular text-muted-foreground">
                          {Math.round(((v - min) / (max - min || 1)) * 100)}%
                        </span>
                      </div>
                      <Slider
                        value={[v]}
                        min={min}
                        max={max}
                        step={(max - min) / 20}
                        disabled={disabled}
                        thumbLabels={[`${q.label}: ${titleCase(d)}`]}
                        onValueChange={([nv]) => set(q.key, { ...obj, [d]: Number(nv.toFixed(3)) })}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </FormField>
        );
      }
      default:
        return (
          <FormField key={q.key} id={id} label={q.label} error={err} required={q.required}>
            <Input
              id={id}
              placeholder={help}
              value={value === undefined || value === null ? "" : String(value)}
              onChange={(e) => set(q.key, e.target.value)}
              aria-invalid={!!err}
              disabled={disabled}
              maxLength={500}
            />
          </FormField>
        );
    }
  };

  const sections: { key: Section; questions: QuestionOut[] }[] = [
    { key: "basics", questions: groups.basics },
    { key: "sell", questions: groups.sell },
    { key: "customers", questions: groups.customers },
    { key: "reputation", questions: groups.reputation },
  ];

  return (
    <div className="space-y-4">
      {sections
        .filter((s) => s.questions.length > 0)
        .map((s) => (
          <Card key={s.key}>
            <CardHeader>
              <CardTitle>{t(`sections.${s.key}.title`)}</CardTitle>
              <CardDescription>{t(`sections.${s.key}.description`)}</CardDescription>
              {/* {s.key === "reputation" ? (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{t("providedByYou")}</span> ·{" "}
                  {t("newBusinessHint")}
                </p>
              ) : null} */}
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">{s.questions.map(renderQuestion)}</CardContent>
          </Card>
        ))}
      <Card>
        <CardHeader>
          <CardTitle>{t("sections.notes.title")}</CardTitle>
          <CardDescription>{t("sections.notes.description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            id="brand_notes"
            aria-label={t("sections.notes.title")}
            value={notes}
            maxLength={1000}
            disabled={disabled}
            onChange={(e) => {
              setNotes(e.target.value);
              set("brand_notes", e.target.value);
            }}
          />
        </CardContent>
      </Card>
    </div>
  );
}
