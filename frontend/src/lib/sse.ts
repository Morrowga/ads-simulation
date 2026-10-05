"use client";

/**
 * useTestProgress: snapshot first, then a Server-Sent Events stream authenticated with a
 * short-lived stream token (EventSource cannot send headers). Reconnects with a fresh token.
 * The reducer keeps at most 200 chart points and 30 comments.
 */
import { useEffect, useReducer } from "react";
import { get, post } from "./api";
import { API_URL } from "./config";
import type { Range } from "./format";
import type { ProgressSnapshot, StreamTokenOut, TestStatus } from "./types";

export const STAGES = [
  "prepare",
  "analyze_ad",
  "population",
  "archetypes",
  "react",
  "simulate",
  "explain",
  "export",
] as const;
export type Stage = (typeof STAGES)[number];

/** Stage stepper groups (5 visible steps, section 7.1). */
export const STEPPER: { key: string; stages: Stage[] }[] = [
  { key: "analysing", stages: ["prepare", "analyze_ad"] },
  { key: "audience", stages: ["population", "archetypes"] },
  { key: "reacting", stages: ["react"] },
  { key: "simulating", stages: ["simulate"] },
  { key: "reasons", stages: ["explain", "export"] },
];

export interface RunRow {
  run: number;
  scenario: string;
  score: number | null;
  ctr: number | null;
  buys: number | null;
  goal_value: number | null;
}

export interface BatchEvent {
  stage: string;
  pct: number;
  runs_done: number;
  runs_target: number;
  platform: string;
  audience_idx: number;
  batch: RunRow[];
  estimate: Estimate;
  funnel: Record<string, number>;
  confidence: string;
}

export interface Estimate {
  score?: Range;
  goal_value?: Range;
  ctr?: Range;
  stop_rate?: Range;
  [key: string]: Range | undefined;
}

export interface ChartPoint {
  run: number;
  p10: number;
  p50: number;
  p90: number;
  score: number | null;
}

export interface LiveComment {
  id: number;
  archetype: string;
  text: string;
  topic: string | null;
  platform: string;
  language_group: string;
}

export interface ComboState {
  platform: string;
  audience_idx: number;
  runs_done: number;
  runs_target: number;
  estimate: Estimate | null;
  funnel: Record<string, number>;
  chart: ChartPoint[];
  batches: BatchEvent[];
}

export interface ProgressState {
  loaded: boolean;
  connected: boolean;
  status: TestStatus | null;
  stage: string | null;
  label: string | null;
  pct: number;
  cancelWindow: boolean;
  runsDone: number;
  runsTarget: number;
  estimate: Estimate | null;
  funnel: Record<string, number>;
  confidence: string | null;
  chart: ChartPoint[];
  batches: BatchEvent[];
  comments: LiveComment[];
  combos: Record<string, ComboState>;
  completed: { score: Range | number | null; report_url: string } | null;
  failed: { code: string; message: string; rerun_available: boolean } | null;
  cancelled: { free_restart: boolean } | null;
  error: Record<string, unknown> | null;
}

export const initialProgress: ProgressState = {
  loaded: false,
  connected: false,
  status: null,
  stage: null,
  label: null,
  pct: 0,
  cancelWindow: true,
  runsDone: 0,
  runsTarget: 0,
  estimate: null,
  funnel: {},
  confidence: null,
  chart: [],
  batches: [],
  comments: [],
  combos: {},
  completed: null,
  failed: null,
  cancelled: null,
  error: null,
};

export type ProgressAction =
  | { type: "snapshot"; s: ProgressSnapshot }
  | { type: "connected"; value: boolean }
  | { type: "stage"; data: { stage: string; pct: number; label?: string; cancel_window: boolean } }
  | { type: "run_batch"; data: BatchEvent }
  | { type: "comment"; data: Omit<LiveComment, "id"> }
  | { type: "completed"; data: { score: Range | number | null; report_url: string } }
  | { type: "failed"; data: { code: string; message: string; rerun_available: boolean } }
  | { type: "cancelled"; data: { free_restart: boolean } };

const MAX_POINTS = 200;
const MAX_COMMENTS = 30;
const MAX_BATCHES = 40;
let commentSeq = 0;

function pointFrom(data: BatchEvent): ChartPoint | null {
  const ctr = data.estimate?.ctr;
  if (!ctr || ctr.p50 === undefined || ctr.p50 === null) return null;
  return {
    run: data.runs_done,
    p10: ctr.p10 ?? ctr.p50,
    p50: ctr.p50,
    p90: ctr.p90 ?? ctr.p50,
    score: data.estimate?.score?.p50 ?? null,
  };
}

function trimPoints(points: ChartPoint[]): ChartPoint[] {
  if (points.length <= MAX_POINTS) return points;
  // keep the most recent points but always keep the first one for the axis
  return [points[0], ...points.slice(points.length - MAX_POINTS + 1)];
}

export function progressReducer(state: ProgressState, action: ProgressAction): ProgressState {
  switch (action.type) {
    case "connected":
      return { ...state, connected: action.value };
    case "snapshot": {
      const s = action.s;
      // a finished test never goes back; a late/stale snapshot must not undo it
      if (state.status === "completed" && s.status !== "completed") {
        return { ...state, loaded: true };
      }
      const sameRun = state.status === "running" && s.status === "running";
      const pct = s.status === "completed" ? 100 : sameRun ? Math.max(state.pct, s.pct) : s.pct;
      return {
        ...state,
        loaded: true,
        status: s.status,
        stage: sameRun ? (s.pct >= state.pct ? s.stage : state.stage) : s.stage,
        label: sameRun ? (s.pct >= state.pct ? (s.label ?? null) : state.label) : (s.label ?? null),
        pct,
        cancelWindow: s.cancel_window,
        runsDone: sameRun ? Math.max(state.runsDone, s.runs_done) : s.runs_done,
        runsTarget: s.runs_target || state.runsTarget,
        estimate: (s.estimate as Estimate | null) ?? state.estimate,
        funnel: (s.funnel as Record<string, number> | null) ?? state.funnel,
        confidence: s.confidence ?? state.confidence,
        error: s.error ?? null,
        completed:
          s.status === "completed"
            ? (state.completed ?? { score: null, report_url: `/tests/${s.test_id}/report` })
            : state.completed,
        failed:
          s.status === "failed"
            ? (state.failed ?? {
                code: String((s.error ?? {}).code ?? "failed"),
                message: String((s.error ?? {}).message ?? ""),
                rerun_available: true,
              })
            : state.failed,
      };
    }
    case "stage":
      return {
        ...state,
        status: "running",
        stage: action.data.stage,
        pct: action.data.pct,
        label: action.data.label ?? state.label,
        cancelWindow: action.data.cancel_window,
      };
    case "run_batch": {
      const d = action.data;
      const point = pointFrom(d);
      const key = `${d.platform}:${d.audience_idx}`;
      const prev = state.combos[key] ?? {
        platform: d.platform,
        audience_idx: d.audience_idx,
        runs_done: 0,
        runs_target: 0,
        estimate: null,
        funnel: {},
        chart: [],
        batches: [],
      };
      const combo: ComboState = {
        ...prev,
        runs_done: d.runs_done,
        runs_target: d.runs_target,
        estimate: d.estimate ?? prev.estimate,
        funnel: d.funnel ?? prev.funnel,
        chart: point ? trimPoints([...prev.chart, point]) : prev.chart,
        batches: [d, ...prev.batches].slice(0, MAX_BATCHES),
      };
      return {
        ...state,
        status: "running",
        stage: d.stage,
        pct: d.pct,
        cancelWindow: false,
        runsDone: d.runs_done,
        runsTarget: d.runs_target,
        estimate: d.estimate ?? state.estimate,
        funnel: d.funnel ?? state.funnel,
        confidence: d.confidence ?? state.confidence,
        chart: point ? trimPoints([...state.chart, point]) : state.chart,
        batches: [d, ...state.batches].slice(0, MAX_BATCHES),
        combos: { ...state.combos, [key]: combo },
      };
    }
    case "comment":
      commentSeq += 1;
      return {
        ...state,
        comments: [{ id: commentSeq, ...action.data }, ...state.comments].slice(0, MAX_COMMENTS),
      };
    case "completed":
      return { ...state, status: "completed", pct: 100, cancelWindow: false, completed: action.data };
    case "failed":
      return { ...state, status: "failed", cancelWindow: false, failed: action.data };
    case "cancelled":
      return { ...state, status: "draft", cancelWindow: false, cancelled: action.data };
    default:
      return state;
  }
}

const EVENTS = ["stage", "run_batch", "comment", "completed", "failed", "cancelled"] as const;

export function useTestProgress(testId: string, enabled = true): ProgressState {
  const [state, dispatch] = useReducer(progressReducer, initialProgress);

  useEffect(() => {
    if (!enabled) return;
    let es: EventSource | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    const stopAll = () => {
      closed = true;
      if (retry) clearTimeout(retry);
      if (poll) clearInterval(poll);
      es?.close();
    };

    // snapshot (initial load AND polling fallback): if SSE misses an event, this still catches up
    const loadSnapshot = () =>
      get<ProgressSnapshot>(`/tests/${testId}/progress/snapshot`)
        .then((s) => {
          if (closed) return;
          dispatch({ type: "snapshot", s });
          const st = String(s.status);
          if (st === "completed" || st === "failed" || st === "refunded") stopAll();
        })
        .catch(() => undefined);

    void loadSnapshot();
    poll = setInterval(() => void loadSnapshot(), 3000);

    const connect = async () => {
      if (closed) return;
      try {
        const { stream_token } = await post<StreamTokenOut>(`/tests/${testId}/progress/token`);
        if (closed) return;
        es = new EventSource(`${API_URL}/tests/${testId}/progress?st=${encodeURIComponent(stream_token)}`);
        es.onopen = () => dispatch({ type: "connected", value: true });
        es.addEventListener("snapshot", (e) =>
          dispatch({ type: "snapshot", s: JSON.parse((e as MessageEvent).data) as ProgressSnapshot }),
        );
        for (const t of EVENTS) {
          es.addEventListener(t, (e) => {
            const data = JSON.parse((e as MessageEvent).data);
            dispatch({ type: t, data } as ProgressAction);
            if (t === "completed" || t === "failed" || t === "cancelled") stopAll();
          });
        }
        es.onerror = () => {
          dispatch({ type: "connected", value: false });
          es?.close();
          if (!closed) retry = setTimeout(connect, 3000);
        };
      } catch {
        dispatch({ type: "connected", value: false });
        if (!closed) retry = setTimeout(connect, 3000);
      }
    };
    void connect();
    return stopAll;
  }, [testId, enabled]);

  return state;
}
