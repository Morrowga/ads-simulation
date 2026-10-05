"use client";

import { ImageIcon, Volume2 } from "lucide-react";
import type { PreviewMedia } from "./types";
import { cn } from "@/lib/utils";

/**
 * Media area. By default sized to a fixed `aspect` (images/videos are letterboxed, never cropped
 * silently) — use this inside a scrolling feed where the box must reserve its own height.
 *
 * Pass `fill` instead of `aspect` for a full-screen takeover (Stories, Reels, TikTok) that's
 * already placed inside a container with a real, definite height (e.g. the phone-frame screen
 * cutout) — it fills exactly that height rather than computing its own from width, which avoids
 * leaving leftover blank space when the container's real proportions aren't a clean 9:16.
 */
export function MediaBox({
  media,
  aspect,
  fill = false,
  className,
  fit = "contain",
  overlay,
}: {
  media: PreviewMedia | null;
  aspect?: string;
  fill?: boolean;
  className?: string;
  fit?: "contain" | "cover";
  overlay?: React.ReactNode;
}) {
  return (
    <div
      className={cn("relative w-full overflow-hidden bg-zinc-900", fill ? "h-full" : undefined, className)}
      style={fill ? undefined : { aspectRatio: aspect }}
    >
      {media ? (
        media.kind === "video" ? (
          <video
            src={media.url}
            className={cn("h-full w-full", fit === "cover" ? "object-cover" : "object-contain")}
            muted
            playsInline
            loop
            autoPlay
            aria-label="Ad video preview"
          />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- previews load user assets from the API host at runtime
          <img
            src={media.url}
            alt=""
            className={cn("h-full w-full", fit === "cover" ? "object-cover" : "object-contain")}
          />
        )
      ) : (
        <div className="flex h-full w-full items-center justify-center text-zinc-500">
          <ImageIcon className="h-10 w-10" aria-hidden />
        </div>
      )}
      {media?.kind === "video" ? (
        <span className="absolute bottom-2 right-2 rounded-full bg-black/60 p-1.5 text-white" aria-hidden>
          <Volume2 className="h-3.5 w-3.5" />
        </span>
      ) : null}
      {overlay}
    </div>
  );
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-300 text-xs font-semibold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-100",
        className,
      )}
      aria-hidden
    >
      {name.trim().slice(0, 1).toUpperCase() || "A"}
    </span>
  );
}

export function SamplePost({
  name,
  text,
  aspect = "4/3",
  compact = false,
}: {
  name: string;
  text: string;
  aspect?: string;
  compact?: boolean;
}) {
  return (
    <article
      className="border-b border-zinc-200 bg-white p-3 text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100"
      aria-hidden
    >
      <div className="flex items-center gap-2">
        <Avatar name={name} />
        <div>
          <p className="text-sm font-semibold">{name}</p>
          <p className="text-xs text-zinc-500">2h</p>
        </div>
      </div>
      <p className="mt-2 text-sm">{text}</p>
      {!compact ? (
        <div className="mt-2 rounded-md bg-zinc-200 dark:bg-zinc-800" style={{ aspectRatio: aspect }} />
      ) : null}
    </article>
  );
}