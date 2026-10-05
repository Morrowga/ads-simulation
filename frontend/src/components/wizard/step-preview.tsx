"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { PlatformPreview, placementCaptionLimit } from "@/components/preview/platform-preview";
import { mediaFromAsset, type PreviewAd } from "@/components/preview/types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { titleCase } from "@/lib/format";
import { usePlatforms } from "@/lib/queries";
import type { TestOut } from "@/lib/types";

export function previewAdFromTest(test: TestOut, fallbackPage: string): PreviewAd {
  const copy = test.ad_copy as {
    caption?: string;
    headline?: string;
    cta?: string;
    link_url?: string | null;
  };
  const snap = (test.profile.snapshot ?? {}) as Record<string, unknown>;
  let host: string | null = null;
  if (copy.link_url) {
    try {
      host = new URL(copy.link_url).host;
    } catch {
      host = null;
    }
  }
  return {
    pageName: String(snap.business_name ?? test.profile.preset_name ?? fallbackPage),
    caption: copy.caption ?? "",
    headline: copy.headline ?? "",
    cta: copy.cta ?? "learn_more",
    postType: test.post_type,
    media: mediaFromAsset(test.assets.find((a) => a.kind === "video") ?? test.assets[0]),
    linkHost: host,
  };
}

export function StepPreview({ test }: { test: TestOut }) {
  const t = useTranslations("wizard.preview");
  const tp = useTranslations("preview");
  const platforms = usePlatforms();
  const ad = useMemo(() => previewAdFromTest(test, t("yourPage")), [test, t]);
  const combos = test.platforms.flatMap((p) =>
    (p.placements.length ? p.placements : ["feed"]).map((pl) => ({
      platform: p.code,
      placement: pl,
      name: p.name ?? titleCase(p.code),
    })),
  );
  const [active, setActive] = useState(combos[0] ? `${combos[0].platform}:${combos[0].placement}` : "");

  if (combos.length === 0) {
    return (
      <Alert variant="warning">
        <AlertDescription>{t("noPlatforms")}</AlertDescription>
      </Alert>
    );
  }

  const activeCombo = combos.find((c) => `${c.platform}:${c.placement}` === active) ?? combos[0];
  const activePlatformInfo = platforms.data?.find((p) => p.code === activeCombo.platform);
  const captionLimit = placementCaptionLimit(activePlatformInfo, activeCombo.placement);

  return (
    <div className="space-y-4">
      {/* <p className="text-sm text-muted-foreground">{t("intro")}</p> */}
      {captionLimit !== null ? (
        <Badge variant={ad.caption.length > captionLimit ? "warning" : "neutral"}>
          {tp("captionChars", { count: ad.caption.length, max: captionLimit })}
        </Badge>
      ) : null}
      <Tabs
        value={active}
        onValueChange={setActive}
        orientation="vertical"
        className="flex flex-col gap-4 sm:flex-row sm:items-start"
      >
        <TabsList className="h-auto w-full flex-row flex-wrap justify-start gap-2 bg-transparent p-0 sm:w-56 sm:shrink-0 sm:flex-col sm:items-stretch sm:overflow-x-visible">
          {combos.map((c) => (
            <TabsTrigger
              key={`${c.platform}:${c.placement}`}
              value={`${c.platform}:${c.placement}`}
              className="w-full justify-start rounded-full border border-border bg-background text-left data-[state=active]:border-primary data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none"
            >
              {c.name} · {titleCase(c.placement)}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="min-w-0 flex-1">
          {combos.map((c) => (
            <TabsContent
              key={`${c.platform}:${c.placement}`}
              value={`${c.platform}:${c.placement}`}
              className="mt-0"
            >
              <PlatformPreview
                platform={c.platform}
                placement={c.placement}
                ad={ad}
                platformInfo={platforms.data?.find((p) => p.code === c.platform)}
              />
            </TabsContent>
          ))}
        </div>
      </Tabs>
    </div>
  );
}