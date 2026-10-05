"use client";

import { MessageCircle, MoreHorizontal, Share2, ThumbsUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { TruncatedCaption } from "./caption";
import { Avatar, MediaBox, SamplePost } from "./media-box";
import { CTA_LABEL, type PreviewAd } from "./types";

export function FacebookFeed({ ad }: { ad: PreviewAd }) {
  const t = useTranslations("preview");
  const sponsored = ad.postType !== "organic";
  return (
    <div className="bg-zinc-100 dark:bg-zinc-900">
      <SamplePost name={t("sample.friend1")} text={t("sample.text1")} />
      <SamplePost name={t("sample.friend2")} text={t("sample.text2")} compact />
      <article
        className="border-b border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100"
        aria-label={t("yourAd")}
      >
        <div className="flex items-center gap-1.5 p-2">
          <Avatar name={ad.pageName} className="h-6 w-6" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold">{ad.pageName}</p>
            <p className="text-[10px] text-zinc-500">{sponsored ? t("sponsored") : t("justNow")}</p>
          </div>
          <MoreHorizontal className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
        </div>
        <TruncatedCaption text={ad.caption} className="px-2 pb-1.5 text-xs" />
        <MediaBox media={ad.media} aspect={ad.media?.kind === "video" ? "4/5" : "1/1"} />
        {sponsored || ad.headline ? (
          <div className="flex items-center gap-2 bg-zinc-100 p-2 dark:bg-zinc-900">
            <div className="min-w-0 flex-1">
              {ad.linkHost ? (
                <p className="truncate text-[9px] uppercase text-zinc-500">{ad.linkHost}</p>
              ) : null}
              <p className="truncate text-xs font-semibold">{ad.headline || " "}</p>
            </div>
            {ad.cta !== "none" && CTA_LABEL[ad.cta] ? (
              <span className="shrink-0 rounded-md bg-zinc-200 px-2 py-1 text-[10px] font-semibold dark:bg-zinc-700">
                {CTA_LABEL[ad.cta]}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="flex justify-around border-t border-zinc-200 px-2 py-1.5 text-[10px] text-zinc-500 dark:border-zinc-800">
          <span className="flex items-center gap-1">
            <ThumbsUp className="h-3.5 w-3.5" aria-hidden /> {t("like")}
          </span>
          <span className="flex items-center gap-1">
            <MessageCircle className="h-3.5 w-3.5" aria-hidden /> {t("comment")}
          </span>
          <span className="flex items-center gap-1">
            <Share2 className="h-3.5 w-3.5" aria-hidden /> {t("share")}
          </span>
        </div>
      </article>
      <SamplePost name={t("sample.friend3")} text={t("sample.text3")} compact />
      <SamplePost name={t("sample.friend4")} text={t("sample.text4")} aspect="1/1" />
    </div>
  );
}

/**
 * 9:16-ish full-screen story card with progress bar and CTA (shared by Facebook- and
 * Instagram-style stories). Uses MediaBox's `fill` mode rather than a fixed 9/16 aspect ratio:
 * it's already placed inside the phone-frame's screen cutout, which has its own real height, and
 * a hardcoded 9:16 box doesn't match that height exactly — the mismatch was showing up as a block
 * of blank space at the bottom. `fill` makes the media stretch to fill whatever height its
 * container actually has, so there's no leftover gap.
 */
export function StoryFrame({ ad }: { ad: PreviewAd }) {
  const t = useTranslations("preview");
  return (
    <MediaBox
      media={ad.media}
      fill
      fit="cover"
      className="bg-black"
      overlay={
        <>
          <div className="absolute inset-x-2 top-1 flex gap-1" aria-hidden>
            <span className="h-0.5 flex-1 rounded bg-white/90" />
            <span className="h-0.5 flex-1 rounded bg-white/40" />
            <span className="h-0.5 flex-1 rounded bg-white/40" />
          </div>
          <div className="absolute inset-x-2 top-4 flex items-center gap-1.5">
            <Avatar name={ad.pageName} className="h-5 w-5 bg-white/80 text-zinc-800" />
            <p className="truncate text-[11px] font-semibold text-white drop-shadow">{ad.pageName}</p>
            {ad.postType !== "organic" ? (
              <span className="text-[9px] text-white/80">{t("sponsored")}</span>
            ) : null}
          </div>
          <div className="absolute inset-x-2 bottom-3 space-y-1.5">
            <TruncatedCaption text={ad.caption} cutoff={80} light className="text-xs text-white drop-shadow" />
            {ad.cta !== "none" && CTA_LABEL[ad.cta] ? (
              <div className="rounded-full bg-white px-3 py-1.5 text-center text-[11px] font-semibold text-zinc-900">
                {CTA_LABEL[ad.cta]}
              </div>
            ) : null}
          </div>
        </>
      }
    />
  );
}