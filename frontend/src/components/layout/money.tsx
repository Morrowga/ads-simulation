"use client";

import { useLocale } from "next-intl";
import { formatMoney } from "@/lib/format";
import type { LocalAmountOut } from "@/lib/types";

/** "$12 = ฿430": USD from the API plus the approximate local amount; never calculated in the browser. */
export function Money({
  usdMinor,
  display,
  local,
  className,
}: {
  usdMinor?: number | null;
  display?: string | null;
  local?: LocalAmountOut | Record<string, unknown> | null;
  className?: string;
}) {
  const locale = useLocale();
  const usd = display ?? formatMoney(usdMinor, "USD", locale);
  const loc = local as LocalAmountOut | null | undefined;
  return (
    <span className={className}>
      <span className="tabular">{usd}</span>
      {loc && loc.currency && loc.currency !== "USD" ? (
        <span className="text-muted-foreground tabular">
          {" "}
          = {loc.display || formatMoney(loc.amount_minor, loc.currency, locale)}
        </span>
      ) : null}
    </span>
  );
}
