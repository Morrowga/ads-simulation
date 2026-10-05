/** Money and number formatting. Amounts always come from the API in minor units + currency code. */
const ZERO_DECIMAL = new Set(["MMK", "JPY", "VND", "IDR", "KRW"]);

export function minorUnits(currency: string): number {
  return ZERO_DECIMAL.has(currency.toUpperCase()) ? 1 : 100;
}

export function formatMoney(
  amountMinor: number | null | undefined,
  currency: string,
  locale = "en",
  approximate = false,
): string {
  if (amountMinor === null || amountMinor === undefined) return "—";
  const cur = currency.toUpperCase();
  const value = amountMinor / minorUnits(cur);
  let text: string;
  try {
    text = new Intl.NumberFormat(locale, {
      style: "currency",
      currency: cur,
      maximumFractionDigits: minorUnits(cur) === 1 ? 0 : 2,
    }).format(value);
  } catch {
    text = `${cur} ${value.toFixed(minorUnits(cur) === 1 ? 0 : 2)}`;
  }
  return approximate ? `= ${text}` : text;
}

export function formatPercent(value: number | null | undefined, digits = 1, locale = "en"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number | null | undefined, locale = "en", digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

export function formatDate(
  value: string | Date | null | undefined,
  locale = "en",
  opts: Intl.DateTimeFormatOptions = { dateStyle: "medium" },
): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, opts).format(d);
}

export function formatDateTime(value: string | Date | null | undefined, locale = "en"): string {
  return formatDate(value, locale, { dateStyle: "medium", timeStyle: "short" });
}

export function formatRelative(value: string | Date | null | undefined, locale = "en"): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  const diff = (d.getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** P10 / P50 / P90 object from the API. */
export interface Range {
  p10?: number | null;
  p50?: number | null;
  p90?: number | null;
  mean?: number | null;
}

export function rangeText(
  r: Range | null | undefined,
  fmt: (v: number) => string = (v) => formatNumber(v),
): string {
  if (!r || r.p50 === null || r.p50 === undefined) return "—";
  const lo = r.p10 ?? r.p50;
  const hi = r.p90 ?? r.p50;
  return `${fmt(lo)} – ${fmt(hi)}`;
}

export type ScoreBand = "weak" | "below" | "average" | "good" | "strong" | "none";

/** Bands match the engine scale: 50 = an average ad, real scores run about 22–75. */
export function scoreBand(score: number | null | undefined): ScoreBand {
  if (score === null || score === undefined) return "none";
  if (score < 30) return "weak";
  if (score < 45) return "below";
  if (score < 60) return "average";
  if (score < 70) return "good";
  return "strong";
}

export function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
