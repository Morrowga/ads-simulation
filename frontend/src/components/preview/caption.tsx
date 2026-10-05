"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { SEE_MORE_CUTOFF } from "./types";

/** Caption with the "See more" truncation so users see what hides behind the fold. */
export function TruncatedCaption({
  text,
  cutoff = SEE_MORE_CUTOFF,
  className,
  light = false,
}: {
  text: string;
  cutoff?: number;
  className?: string;
  light?: boolean;
}) {
  const t = useTranslations("preview");
  const [open, setOpen] = useState(false);
  if (!text) return <p className={className}>&nbsp;</p>;
  const long = text.length > cutoff;
  const shown = open || !long ? text : text.slice(0, cutoff).trimEnd() + "…";
  return (
    <p className={className} style={{ whiteSpace: "pre-wrap" }}>
      {shown}
      {long ? (
        <>
          {" "}
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className={light ? "font-semibold text-white/90" : "font-semibold text-zinc-500"}
          >
            {open ? t("seeLess") : t("seeMore")}
          </button>
        </>
      ) : null}
    </p>
  );
}
