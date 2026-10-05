"use client";

/** Summary cards of a test's inputs, reused by the overview and confirm pages. Each card links to its wizard step. */
import { Pencil } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Money } from "@/components/layout/money";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { formatDate, formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { AudienceIn, TestOut } from "@/lib/types";

function EditLink({
  testId,
  step,
  editable,
  label,
}: {
  testId: string;
  step: number;
  editable: boolean;
  label: string;
}) {
  if (!editable) return null;
  return (
    <Button asChild variant="ghost" size="sm" className="-mr-2 -mt-1 h-8">
      <Link href={`/tests/new?id=${testId}&step=${step}`} aria-label={label}>
        <Pencil aria-hidden /> {label}
      </Link>
    </Button>
  );
}

export function TestSummaryCards({
  test,
  editable,
  priceUsdMinor,
  priceLocal,
}: {
  test: TestOut;
  editable: boolean;
  priceUsdMinor?: number | null;
  priceLocal?: Record<string, unknown> | null;
}) {
  const t = useTranslations("testSummary");
  const locale = useLocale();
  const copy = test.ad_copy as { caption?: string; headline?: string; cta?: string };
  const sched = test.schedule as {
    start_date?: string | null;
    days?: number;
    post_at?: string | null;
    observe_days?: number;
  };
  const audiences = (test.audiences ?? []) as AudienceIn[];
  const media = test.assets[0];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>{t("ad")}</CardTitle>
          <EditLink testId={test.id} step={1} editable={editable} label={t("edit")} />
        </CardHeader>
        <CardContent className="flex gap-4">
          <div className="h-20 w-20 shrink-0 overflow-hidden rounded-md bg-zinc-900">
            {media?.url ? (
              media.kind === "video" ? (
                <video
                  src={media.url}
                  className="h-full w-full object-cover"
                  muted
                  playsInline
                  aria-label={t("mediaVideo")}
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- asset URL from the API
                <img src={media.url} alt="" className="h-full w-full object-cover" />
              )
            ) : null}
          </div>
          <div className="min-w-0 space-y-1 text-sm">
            <p className="font-medium">{test.title}</p>
            {copy.headline ? <p className="truncate">{copy.headline}</p> : null}
            <p className="line-clamp-3 text-muted-foreground">{copy.caption || t("noCaption")}</p>
            <p className="text-xs text-muted-foreground">
              {t("cta")}: {titleCase(copy.cta ?? "learn_more")} ·{" "}
              {t("mediaCount", { count: test.assets.length })}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>{t("preset")}</CardTitle>
          <EditLink testId={test.id} step={0} editable={editable} label={t("edit")} />
        </CardHeader>
        <CardContent className="text-sm">
          {test.profile.preset_name ? (
            <p>
              {test.profile.preset_name} · v{test.profile.version}
              {test.profile.mode === "one_time" ? (
                <Badge variant="warning" className="ml-2">
                  {t("editedForThisAd")}
                </Badge>
              ) : null}
            </p>
          ) : (
            <p className="text-muted-foreground">{t("noPreset")}</p>
          )}
          {test.profile.snapshot ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {String((test.profile.snapshot as Record<string, unknown>).business_name ?? "")}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>{t("audience")}</CardTitle>
          <EditLink testId={test.id} step={2} editable={editable} label={t("edit")} />
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            {t("country")}: <span className="font-medium">{test.country_code}</span>
          </p>
          {audiences.map((a, i) => (
            <p key={i} className="text-muted-foreground">
              <span className="font-medium text-foreground">{a.name}</span> · {a.targeting?.location || "—"} ·{" "}
              {a.targeting?.age_min}–{(a.targeting?.age_max ?? 99) >= 65 ? "65+" : a.targeting?.age_max} ·{" "}
              {(a.targeting?.genders ?? []).join("/")}
              {a.targeting?.languages?.length ? ` · ${a.targeting.languages.join(", ")}` : ""}
            </p>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <CardTitle>{t("platforms")}</CardTitle>
          <EditLink testId={test.id} step={3} editable={editable} label={t("edit")} />
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p>
            {titleCase(test.post_type)} · {t("goal")}: {titleCase(test.goal)} · {t("tier")}:{" "}
            {titleCase(test.tier_code)}
          </p>
          {test.platforms.length === 0 ? <p className="text-muted-foreground">{t("noPlatforms")}</p> : null}
          {test.platforms.map((p) => (
            <p key={p.code} className="text-muted-foreground">
              <span className="font-medium text-foreground">{p.name ?? titleCase(p.code)}</span> ·{" "}
              {p.placements.map(titleCase).join(", ")}
              {test.platforms.length > 1 ? ` · ${Math.round(p.budget_share)}%` : ""}
            </p>
          ))}
          <p className="text-muted-foreground">
            {test.post_type === "organic"
              ? t("organicSchedule", {
                  at: formatDateTime(sched.post_at, locale),
                  days: sched.observe_days ?? 3,
                })
              : t("paidSchedule", { date: formatDate(sched.start_date, locale), days: sched.days ?? 3 })}
          </p>
          {test.post_type !== "organic" ? (
            <p>
              {t("budget")}:{" "}
              <span className="font-medium tabular">
                {formatMoney(test.budget_minor, test.currency, locale)}
              </span>
            </p>
          ) : null}
          {priceUsdMinor !== undefined && priceUsdMinor !== null ? (
            <p>
              {t("price")}:{" "}
              <Money usdMinor={priceUsdMinor} local={priceLocal ?? null} className="font-medium" />
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
