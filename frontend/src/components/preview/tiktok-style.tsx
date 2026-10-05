"use client";

import { Bookmark, Heart, MessageCircle, Share2, Volume2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { TruncatedCaption } from "./caption";
import { Avatar, MediaBox } from "./media-box";
import { CTA_LABEL, type PreviewAd } from "./types";

export function TikTokInFeed({ ad }: { ad: PreviewAd }) {
  const t = useTranslations("preview");
  return (
    <MediaBox
      media={ad.media}
      fill
      fit="cover"
      className="bg-black"
      overlay={
        <>
          <div className="absolute right-2 top-1/2 flex flex-col items-center gap-4 text-white" aria-hidden>
            <Avatar name={ad.pageName} className="h-9 w-9 bg-white text-zinc-800" />
            <Heart className="h-7 w-7" />
            <MessageCircle className="h-7 w-7" />
            <Bookmark className="h-7 w-7" />
            <Share2 className="h-7 w-7" />
          </div>
          <div className="absolute left-3 top-3 flex items-center gap-1 rounded-full bg-black/50 px-2 py-1 text-[10px] text-white">
            <Volume2 className="h-3 w-3" aria-hidden /> {t("soundOn")}
          </div>
          <div className="absolute inset-x-3 bottom-4 max-w-[78%] space-y-2 text-white">
            <p className="text-sm font-semibold drop-shadow">
              @{ad.pageName.replace(/\s+/g, "").toLowerCase() || "yourpage"}
            </p>
            <TruncatedCaption text={ad.caption} cutoff={80} light className="text-xs drop-shadow" />
            {ad.postType !== "organic" ? (
              <span className="inline-block rounded bg-white/20 px-1.5 py-0.5 text-[10px]">
                {t("sponsored")}
              </span>
            ) : null}
            {ad.cta !== "none" && CTA_LABEL[ad.cta] ? (
              <div className="rounded-md bg-rose-500 px-3 py-2 text-center text-xs font-semibold">
                {CTA_LABEL[ad.cta]}
              </div>
            ) : null}
          </div>
        </>
      }
    />
  );
}