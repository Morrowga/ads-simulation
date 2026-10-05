import type { AssetOut } from "@/lib/types";

/** Everything a preview needs; the wizard, confirm page and report all pass this shape. */
export interface PreviewAd {
  pageName: string;
  caption: string;
  headline: string;
  cta: string;
  postType: "paid" | "boosted" | "organic";
  media: PreviewMedia | null;
  linkHost?: string | null;
}

export interface PreviewMedia {
  kind: "image" | "video";
  url: string;
  width?: number | null;
  height?: number | null;
  durationS?: number | null;
}

export function mediaFromAsset(a: AssetOut | undefined): PreviewMedia | null {
  if (!a || !a.url) return null;
  return {
    kind: a.kind === "video" ? "video" : "image",
    url: a.url,
    width: a.width,
    height: a.height,
    durationS: a.duration_s,
  };
}

/** Aspect ratio label like "1:1", "4:5", "9:16", "16:9" from the media dimensions (closest match). */
export function ratioLabel(w?: number | null, h?: number | null): string | null {
  if (!w || !h) return null;
  const r = w / h;
  const known: [string, number][] = [
    ["1:1", 1],
    ["4:5", 0.8],
    ["9:16", 9 / 16],
    ["16:9", 16 / 9],
    ["4:3", 4 / 3],
    ["3:4", 3 / 4],
    ["1.91:1", 1.91],
  ];
  let best = known[0];
  for (const k of known) if (Math.abs(k[1] - r) < Math.abs(best[1] - r)) best = k;
  return best[0];
}

export const CTA_LABEL: Record<string, string> = {
  learn_more: "Learn more",
  shop_now: "Shop now",
  send_message: "Send message",
  order_now: "Order now",
  sign_up: "Sign up",
  book_now: "Book now",
  get_offer: "Get offer",
  none: "",
};

export const SEE_MORE_CUTOFF = 125;
