/** Typed views over the untyped parts of ReportOut (the backend's report JSON maps 1:1 to these). */
import type { Range } from "@/lib/format";
import type { ReportOut } from "@/lib/types";

export type Dict = Record<string, unknown>;
export type SegmentRow = { seen: number; [k: string]: number };
export type SegmentTable = Record<string, SegmentRow>;
export type Segments = Record<string, SegmentTable>;

export interface ReportSummary {
  score: number | null;
  score_range: Range | null;
  goal: string;
  goal_metric: string;
  goal_rate_key: string;
  goal_value: Range | null;
  goal_rate: Range | null;
  rates: Record<string, Range> | null;
  counts: Record<string, Range> | null;
  sentiment: Range | null;
  population_per_platform: number | null;
  scale: number | null;
  runs_total: number;
  caption_language: string | null;
  caption_english: string | null;
  scenarios: { code?: string; name?: string; weight?: number }[];
  cost_usd?: number;
  llm_calls?: number;
  post_type: string;
  budget_usd: number | null;
  variety_alerts: Dict;
  ad_image: {
    impressed_share: number;
    not_impressed_share: number;
    top_first_impressions: { text: string; weight: number }[];
  };
  caption: { read_share: number; ignored_share: number; language: string | null; english: string | null };
  ad_features: Dict;
}

export interface Headline {
  metric: string;
  label: string;
  value: Range | null;
  rate_key: string;
  rate: Range | null;
  estimated_people: Record<string, number>;
}

export interface Funnel {
  seen: number;
  skipped: number;
  stopped: number;
  reacted: number;
  commented: number;
  shared: number;
  saved: number;
  clicked: number;
  messaged: number;
  bought: number;
  population: number;
  estimated_people: Record<string, number>;
}

export interface Timing {
  ticks: number;
  hourly_seen: number[];
  hourly_stops: number[];
  hourly_clicks: number[];
  peak_tick?: number;
  daily_reach?: number[];
  hour_of_day_stops?: number[];
  first_24h_reach_share?: number;
}
export interface Fatigue {
  seen_by_exposure: number[];
  stops_by_exposure: number[];
  stop_rate_by_exposure: number[];
  mean_frequency: number;
  capped_share: number;
}
export interface Dropoff {
  offer_visible_at_s: number | null;
  impatient_left_share: number;
  all_left_before_offer_share: number;
  avg_watch_s: number;
  impatient_ctr: number;
  patient_ctr: number;
}
export interface Taste {
  mismatch_share_of_seen?: number;
  mismatch_stop_rate?: number;
  match_stop_rate?: number;
  mismatch_negative_share?: number;
  dimensions?: string[];
}
export interface ShareCount {
  count: number;
  share: number;
}

export interface ReportPlatform {
  code: string;
  name: string;
  status: "full" | "beta" | "planned";
  audience_idx: number;
  audience_name: string;
  budget_share: number | null;
  runs: number;
  score: Range | null;
  score_components: {
    component: string;
    metric: string;
    value: number;
    benchmark: number | null;
    normalised: number;
    weight: number;
  }[];
  goal_value: Range;
  goal_rate: Range;
  rates: Record<string, Range>;
  counts: Record<string, Range>;
  funnel: Funnel;
  benchmarks: Record<string, number>;
  scenarios: Record<string, Range>;
  blockers: Record<string, ShareCount>;
  comment_topics: Record<string, ShareCount>;
  dropoff: Dropoff;
  fatigue: Fatigue;
  taste: Taste;
  timing: Timing;
  segments: Segments;
}

export interface ReportAudience {
  audience_idx: number;
  name: string;
  targeting: Dict;
  score: Range | null;
  goal_value: Range | null;
  rates: Record<string, Range> | null;
  counts: Record<string, Range> | null;
  evidence_ids: string[];
}

export interface LanguageGroupRow {
  code: string;
  name: string;
  seen: number;
  stopped: number;
  clicked: number;
  commented: number;
  comments: number;
  reactions_positive: number;
  reactions_negative: number;
  stop_rate: number;
  ctr: number;
}

export interface TypedReport {
  raw: ReportOut;
  summary: ReportSummary;
  headline: Headline;
  funnel: Funnel;
  platforms: ReportPlatform[];
  audiences: ReportAudience[];
  segments: Record<string, Segments>;
  brand: Record<string, SegmentTable>;
  awarenessInputs: Record<string, unknown>;
  timing: Record<string, { timing: Timing; fatigue: Fatigue; dropoff: Dropoff }>;
  languageGroups: LanguageGroupRow[];
}

export function typedReport(r: ReportOut): TypedReport {
  const seg = (r.segments as { per_platform?: Record<string, Segments> }).per_platform ?? {};
  const brandAll = r.brand_relationship as Record<string, unknown>;
  const brand: Record<string, SegmentTable> = {};
  for (const [k, v] of Object.entries(brandAll)) if (k !== "awareness_inputs") brand[k] = v as SegmentTable;
  return {
    raw: r,
    summary: r.summary as unknown as ReportSummary,
    headline: r.headline_metric as unknown as Headline,
    funnel: r.funnel as unknown as Funnel,
    platforms: r.platforms as unknown as ReportPlatform[],
    audiences: r.audiences as unknown as ReportAudience[],
    segments: seg,
    brand,
    awarenessInputs: (brandAll.awareness_inputs as Record<string, unknown>) ?? {},
    timing: r.timing as unknown as Record<string, { timing: Timing; fatigue: Fatigue; dropoff: Dropoff }>,
    languageGroups: r.language_groups as unknown as LanguageGroupRow[],
  };
}

export const FUNNEL_ORDER: (keyof Funnel)[] = [
  "seen",
  "skipped",
  "stopped",
  "reacted",
  "commented",
  "clicked",
  "bought",
];

/** Which reason sections explain which funnel step. */
export const FUNNEL_REASON_SECTIONS: Record<string, string[]> = {
  seen: ["reach"],
  skipped: ["attention", "dropoff"],
  stopped: ["attention"],
  reacted: ["taste", "segments"],
  commented: ["comments", "language"],
  clicked: ["segments", "brand"],
  bought: ["blockers"],
  messaged: ["blockers", "comments"],
};

export const BRAND_ORDER = ["unaware", "aware_not_tried", "tried_liked", "tried_disliked", "regular"];
export const BLOCKER_ORDER = ["price", "shipping", "size", "trust", "relevance"];
