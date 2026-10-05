import { describe, expect, it } from "vitest";
import { initialProgress, progressReducer, type BatchEvent } from "@/lib/sse";

const batch = (n: number, ctr = 0.02): BatchEvent => ({
  stage: "simulate",
  pct: 50,
  runs_done: n,
  runs_target: 150,
  platform: "facebook",
  audience_idx: 0,
  batch: [{ run: n, scenario: "normal", score: 60, ctr, buys: 3, goal_value: 3 }],
  estimate: { score: { p10: 50, p50: 60, p90: 70 }, ctr: { p10: ctr - 0.005, p50: ctr, p90: ctr + 0.005 } },
  funnel: { seen: 1000, stopped: 300, clicked: 20 },
  confidence: "building",
});

describe("progressReducer", () => {
  it("applies the snapshot", () => {
    const s = progressReducer(initialProgress, {
      type: "snapshot",
      s: {
        test_id: "t",
        status: "running",
        stage: "react",
        pct: 40,
        cancel_window: true,
        runs_done: 0,
        runs_target: 150,
      },
    });
    expect(s.loaded).toBe(true);
    expect(s.stage).toBe("react");
    expect(s.cancelWindow).toBe(true);
  });
  it("keeps at most 200 chart points", () => {
    let s = initialProgress;
    for (let i = 1; i <= 260; i++) s = progressReducer(s, { type: "run_batch", data: batch(i) });
    expect(s.chart.length).toBe(200);
    expect(s.chart[0].run).toBe(1);
    expect(s.chart[s.chart.length - 1].run).toBe(260);
    expect(s.cancelWindow).toBe(false);
    expect(s.combos["facebook:0"].runs_done).toBe(260);
  });
  it("keeps at most 30 comments, newest first", () => {
    let s = initialProgress;
    for (let i = 1; i <= 35; i++)
      s = progressReducer(s, {
        type: "comment",
        data: { archetype: "a", text: `c${i}`, topic: "price", platform: "facebook", language_group: "my" },
      });
    expect(s.comments.length).toBe(30);
    expect(s.comments[0].text).toBe("c35");
  });
  it("handles completed, failed and cancelled", () => {
    expect(
      progressReducer(initialProgress, { type: "completed", data: { score: 70, report_url: "/r" } }).status,
    ).toBe("completed");
    expect(
      progressReducer(initialProgress, {
        type: "failed",
        data: { code: "x", message: "m", rerun_available: true },
      }).failed?.rerun_available,
    ).toBe(true);
    expect(progressReducer(initialProgress, { type: "cancelled", data: { free_restart: true } }).status).toBe(
      "draft",
    );
  });
});
