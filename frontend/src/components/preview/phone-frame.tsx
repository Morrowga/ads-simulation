"use client";

import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Wraps preview content inside the phone.webp mock-up frame (public/assets/phone.webp).
 *
 * Every dimension here is computed as a plain pixel number in JS (from the image's real,
 * loaded width/height), not left to CSS percentage resolution. Percentages on an absolutely
 * positioned box measured against an auto-height ancestor are not reliably resolved by every
 * browser, and padding percentages are always resolved against the container's WIDTH even for
 * top/bottom — both are easy to get subtly wrong. Plain px math sidesteps all of that: once the
 * frame image loads, we know its exact rendered width and height, so the "screen" cutout and its
 * padding are set as exact pixel values, guaranteed to clip correctly.
 *
 * If the screen cutout doesn't line up with the bezel in your phone.webp, tune INSET_PCT and
 * NOTCH_CLEARANCE_PCT below (fractions of the frame's width/height, used only to compute the
 * one-time pixel values).
 */
const FRAME_WIDTH = 264;
// Height stays pinned to what it was at the frame's original 240px width, so widening
// FRAME_WIDTH above doesn't grow the height too — it only makes the frame (and the screen
// cutout inside it) a bit wider. This does mean the phone.webp image itself is stretched
// slightly horizontally rather than scaled proportionally; at this small a bump (240 -> 264)
// it shouldn't be visually obvious, but if it starts looking squashed, reduce FRAME_WIDTH again.
const HEIGHT_BASIS_WIDTH = 240;
const INSET_PCT = { top: 0.02, bottom: 0.02, left: 0.02, right: 0.02 };
const NOTCH_CLEARANCE_PCT = 0.09;

export function PhoneFrame({ children, className }: { children: ReactNode; className?: string }) {
  const [naturalRatio, setNaturalRatio] = useState<number | null>(null); // height / width

  const frameHeight = naturalRatio ? Math.round(HEIGHT_BASIS_WIDTH * naturalRatio) : null;

  return (
    <div
      className={cn("relative mx-auto", className)}
      style={{ width: FRAME_WIDTH, height: frameHeight ?? undefined }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- local static asset; onLoad reads its real size */}
      <img
        src="/assets/phone.webp"
        alt=""
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 h-full w-full select-none"
        onLoad={(e) => {
          const img = e.currentTarget;
          if (img.naturalWidth && img.naturalHeight) setNaturalRatio(img.naturalHeight / img.naturalWidth);
        }}
      />
      {frameHeight ? (
        <div
          className="absolute overflow-hidden rounded-[9%] bg-background"
          style={{
            top: Math.round(frameHeight * INSET_PCT.top),
            bottom: Math.round(frameHeight * INSET_PCT.bottom),
            left: Math.round(FRAME_WIDTH * INSET_PCT.left),
            right: Math.round(FRAME_WIDTH * INSET_PCT.right),
          }}
        >
          <div
            className="h-full w-full overflow-y-auto px-[3%]"
            style={{ paddingTop: Math.round(frameHeight * NOTCH_CLEARANCE_PCT) }}
          >
            {children}
          </div>
        </div>
      ) : null}
    </div>
  );
}