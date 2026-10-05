"use client";

import { HelpCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { EvidenceOut, ReasonOut } from "@/lib/types";

const PLATFORM_LABEL: Record<string, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};
const platformLabel = (p: string) => PLATFORM_LABEL[p.toLowerCase()] ?? titleCase(p);

const PILL =
  "rounded-full border border-border px-4 py-1.5 text-sm font-medium data-[state=active]:border-[#0071b5] data-[state=active]:bg-[#0071b5] data-[state=active]:text-white data-[state=active]:shadow-none";

function fmtValue(k: string, v: unknown, locale: string): string | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") {
    if (/rate|share|ctr|cvr|pct/.test(k) && v <= 1) return formatPercent(v, 1, locale);
    return formatNumber(v, locale, Number.isInteger(v) ? 0 : 2);
  }
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" ? "" : String(x))).filter(Boolean).join(", ") || null;
  if (typeof v === "object") return null;
  return String(v);
}

function EvidenceCard({ e, locale, showPlatform }: { e: EvidenceOut; locale: string; showPlatform: boolean }) {
  const t = useTranslations("report.evidence");
  const rows = Object.entries(e.values ?? {})
    .map(([k, v]) => [k, fmtValue(k, v, locale)] as const)
    .filter((r): r is readonly [string, string] => r[1] !== null)
    .slice(0, 8);
  return (
    <div className="space-y-3 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="neutral">{titleCase(e.type)}</Badge>
        {showPlatform && e.platform ? <Badge variant="outline">{platformLabel(e.platform)}</Badge> : null}
        {e.audience_idx !== null && e.audience_idx !== undefined ? (
          <Badge variant="outline">{t("audience", { n: e.audience_idx + 1 })}</Badge>
        ) : null}
      </div>
      <p className="text-sm">{e.statement}</p>
      {rows.length > 0 ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border pt-3 text-sm">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{titleCase(k)}</dt>
              <dd className="tabular text-right font-medium">{v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

/** "Why?" → a large dialog: one tab per platform, each tab showing that platform's evidence card. */
export function EvidencePopover({ reason, evidence }: { reason: ReasonOut; evidence: EvidenceOut[] }) {
  const t = useTranslations("report.evidence");
  const locale = useLocale();
  const items = reason.evidence_ids
    .map((id) => evidence.find((e) => e.id === id))
    .filter((e): e is EvidenceOut => !!e);

  const shared = items.filter((e) => !e.platform);
  const platforms: string[] = [];
  for (const e of items) if (e.platform && !platforms.includes(e.platform)) platforms.push(e.platform);
  const tabbed = platforms.length > 1;

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="link" size="sm" className="h-auto px-0 py-0 text-xs">
          <HelpCircle className="h-3.5 w-3.5" aria-hidden /> {t("why")}
        </Button>
      </DialogTrigger>
      <DialogContent className="flex max-h-[90vh] w-[calc(100%-2rem)] max-w-4xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border p-6 pr-12">
          <DialogTitle className="text-base leading-snug sm:text-lg">{reason.statement}</DialogTitle>
          <DialogDescription>{t("confidence", { pct: Math.round(reason.confidence * 100) })}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {items.length === 0 ? <p className="text-sm text-muted-foreground">{t("none")}</p> : null}

          {tabbed ? (
            <div className="space-y-4">
              {shared.map((e) => (
                <EvidenceCard key={e.id} e={e} locale={locale} showPlatform={false} />
              ))}
              <Tabs defaultValue={platforms[0]}>
                <TabsList className="h-auto flex-wrap justify-start gap-2 bg-transparent p-0">
                  {platforms.map((p) => (
                    <TabsTrigger key={p} value={p} className={PILL}>
                      {platformLabel(p)}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {platforms.map((p) => (
                  <TabsContent key={p} value={p} className="mt-4 space-y-4">
                    {items
                      .filter((e) => e.platform === p)
                      .map((e) => (
                        <EvidenceCard key={e.id} e={e} locale={locale} showPlatform={false} />
                      ))}
                  </TabsContent>
                ))}
              </Tabs>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {items.map((e) => (
                <EvidenceCard key={e.id} e={e} locale={locale} showPlatform />
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** The statement, then the "why?" dialog trigger on its own row — for embedding inside an existing <li>. */
export function ReasonContent({ reason, evidence }: { reason: ReasonOut; evidence: EvidenceOut[] }) {
  return (
    <span className="flex min-w-0 flex-col items-start gap-0.5">
      <span>{reason.statement}</span>
      <EvidencePopover reason={reason} evidence={evidence} />
    </span>
  );
}

/** A reason line with its evidence dialog, wrapped in its own <li> — use inside a bare <ul>. */
export function ReasonLine({ reason, evidence }: { reason: ReasonOut; evidence: EvidenceOut[] }) {
  return (
    <li className="text-sm">
      <ReasonContent reason={reason} evidence={evidence} />
    </li>
  );
}