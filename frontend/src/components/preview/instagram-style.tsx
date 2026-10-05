"use client";

import { Bookmark, Heart, MessageCircle, Music2, Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { TruncatedCaption } from "./caption";
import { Avatar, MediaBox } from "./media-box";
import { CTA_LABEL, type PreviewAd } from "./types";

export function InstagramFeed({ ad }: { ad: PreviewAd }) {
  const t = useTranslations("preview");
  return (
    <div className="bg-white text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="flex items-center gap-2 p-3">
        <Avatar name={ad.pageName} className="h-8 w-8" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{ad.pageName}</p>
          {ad.postType !== "organic" ? <p className="text-xs text-zinc-500">{t("sponsored")}</p> : null}
        </div>
      </div>
      <MediaBox media={ad.media} aspect="4/5" />
      {ad.postType !== "organic" && ad.cta !== "none" && CTA_LABEL[ad.cta] ? (
        <div className="flex items-center justify-between bg-zinc-800 px-3 py-2 text-xs font-semibold text-white">
          {CTA_LABEL[ad.cta]}
          <span aria-hidden>›</span>
        </div>
      ) : null}
      <div className="flex items-center gap-4 px-3 py-2 text-zinc-700 dark:text-zinc-300">
        <Heart className="h-5 w-5" aria-hidden />
        <MessageCircle className="h-5 w-5" aria-hidden />
        <Send className="h-5 w-5" aria-hidden />
        <Bookmark className="ml-auto h-5 w-5" aria-hidden />
      </div>
      <div className="px-3 pb-3 text-sm">
        <span className="font-semibold">{ad.pageName} </span>
        <TruncatedCaption text={[ad.headline, ad.caption].filter(Boolean).join(" · ")} className="inline" />
      </div>
    </div>
  );
}

export function InstagramReel({ ad }: { ad: PreviewAd }) {
  const t = useTranslations("preview");
  return (
    <MediaBox
      media={ad.media}
      fill
      fit="cover"
      className="bg-black"
      overlay={
        <>
          <div className="absolute bottom-4 right-2 flex flex-col items-center gap-4 text-white" aria-hidden>
            <Heart className="h-6 w-6" />
            <MessageCircle className="h-6 w-6" />
            <Send className="h-6 w-6" />
            <Bookmark className="h-6 w-6" />
          </div>
          <div className="absolute inset-x-3 bottom-4 max-w-[80%] space-y-2 text-white">
            <div className="flex items-center gap-2">
              <Avatar name={ad.pageName} className="h-7 w-7 bg-white/80 text-zinc-800" />
              <p className="truncate text-xs font-semibold">{ad.pageName}</p>
              {ad.postType !== "organic" ? (
                <span className="text-[10px] text-white/80">{t("sponsored")}</span>
              ) : null}
            </div>
            <TruncatedCaption text={ad.caption} cutoff={80} light className="text-xs drop-shadow" />
            {ad.cta !== "none" && CTA_LABEL[ad.cta] ? (
              <div className="rounded-md bg-white/90 px-3 py-1.5 text-center text-xs font-semibold text-zinc-900">
                {CTA_LABEL[ad.cta]}
              </div>
            ) : null}
            <p className="flex items-center gap-1 text-[11px] text-white/80">
              <Music2 className="h-3 w-3" aria-hidden /> {t("originalAudio")}
            </p>
          </div>
        </>
      }
    />
  );
}