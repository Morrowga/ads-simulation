"use client";

/**
 * One interface for every platform/placement preview. New platforms only add a case here;
 * the wizard, confirm page and report never change. Neutral colours, generic icons, no logos.
 */
import type { PlatformOut } from "@/lib/types";
import { FacebookFeed, StoryFrame } from "./facebook-style";
import { InstagramFeed, InstagramReel } from "./instagram-style";
import { PhoneFrame } from "./phone-frame";
import { TikTokInFeed } from "./tiktok-style";
import type { PreviewAd } from "./types";

/** Caption character limit for a given platform+placement, or null if unlimited/unknown. */
export function placementCaptionLimit(
  platformInfo: PlatformOut | undefined,
  placement: string,
): number | null {
  return platformInfo?.placements.find((x) => x.code === placement)?.max_caption_chars ?? null;
}

export function PlatformPreview({
  platform,
  placement,
  ad,
}: {
  platform: string;
  placement: string;
  ad: PreviewAd;
  platformInfo?: PlatformOut;
}) {
  const p = platform.toLowerCase();
  const pl = placement.toLowerCase();
  let body: React.ReactNode;
  if (p === "facebook") body = pl.includes("stor") ? <StoryFrame ad={ad} /> : <FacebookFeed ad={ad} />;
  else if (p === "instagram")
    body = pl.includes("reel") ? (
      <InstagramReel ad={ad} />
    ) : pl.includes("stor") ? (
      <StoryFrame ad={ad} />
    ) : (
      <InstagramFeed ad={ad} />
    );
  else if (p === "tiktok") body = <TikTokInFeed ad={ad} />;
  else body = <FacebookFeed ad={ad} />;

  // The old label/spec row (platform+placement name, ratio-mismatch badge, caption-limit
  // badge, video-length badge) used to render here above the mock-up. Removed 2026-09-29 so
  // the right-hand pane is just the mock-up itself; the caption counter now lives above the
  // tab list instead (see StepPreview). Kept here, commented, in case it's wanted back:
  //
  // const t = useTranslations("preview");
  // const placementInfo = platformInfo?.placements.find((x) => x.code === placement);
  // const mediaRatio = ratioLabel(ad.media?.width, ad.media?.height);
  // const supported = placementInfo?.ratios ?? [];
  // const cropped = mediaRatio && supported.length > 0 && !supported.includes(mediaRatio);
  // const captionLimit = placementInfo?.max_caption_chars ?? null;
  // const overLimit = captionLimit !== null && ad.caption.length > captionLimit;
  // const videoLimits = placementInfo?.video_s ?? null;
  // const tooLong =
  //   ad.media?.kind === "video" &&
  //   videoLimits &&
  //   ad.media.durationS &&
  //   ad.media.durationS > Math.max(...videoLimits);
  //
  // <div className="flex flex-wrap items-center gap-2 text-sm">
  //   <span className="font-medium">
  //     {t("label", { platform: platformInfo?.name ?? titleCase(platform), placement: titleCase(placement) })}
  //   </span>
  //   {platformInfo?.status === "beta" ? <Badge variant="warning">{t("beta")}</Badge> : null}
  //   {mediaRatio ? (
  //     <Badge variant={cropped ? "warning" : "neutral"}>
  //       {cropped
  //         ? t("specCropped", { ratio: mediaRatio, platform: platformInfo?.name ?? titleCase(platform) })
  //         : t("specRatio", { ratio: mediaRatio })}
  //     </Badge>
  //   ) : null}
  //   {captionLimit !== null ? (
  //     <Badge variant={overLimit ? "warning" : "neutral"}>
  //       {t("captionChars", { count: ad.caption.length, max: captionLimit })}
  //     </Badge>
  //   ) : null}
  //   {tooLong ? (
  //     <Badge variant="warning">
  //       {t("videoLong", { seconds: Math.round(ad.media?.durationS ?? 0), max: Math.max(...(videoLimits ?? [0])) })}
  //     </Badge>
  //   ) : null}
  // </div>

  return <PhoneFrame>{body}</PhoneFrame>;
}