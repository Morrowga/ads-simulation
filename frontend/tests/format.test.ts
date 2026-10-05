import { describe, expect, it } from "vitest";
import { formatMoney, formatPercent, rangeText, scoreBand } from "@/lib/format";

describe("formatMoney", () => {
  it("formats minor units with the currency code from the API", () => {
    expect(formatMoney(1200, "USD")).toBe("$12.00");
  });
  it("treats MMK as zero-decimal", () => {
    expect(formatMoney(35000, "MMK").replace(/ /g, " ")).toMatch(/35,000/);
  });
  it("marks approximate local amounts", () => {
    expect(formatMoney(43000, "THB", "en", true).startsWith("=")).toBe(true);
  });
  it("returns a dash for missing values", () => {
    expect(formatMoney(null, "USD")).toBe("—");
  });
});

describe("scoreBand", () => {
  it("maps 0–39 red, 40–69 amber, 70–100 green", () => {
    expect(scoreBand(0)).toBe("low");
    expect(scoreBand(39)).toBe("low");
    expect(scoreBand(40)).toBe("mid");
    expect(scoreBand(69)).toBe("mid");
    expect(scoreBand(70)).toBe("high");
    expect(scoreBand(100)).toBe("high");
    expect(scoreBand(null)).toBe("none");
  });
});

describe("rangeText / formatPercent", () => {
  it("renders P10–P90 ranges", () => {
    expect(rangeText({ p10: 10, p50: 20, p90: 30 })).toBe("10 – 30");
  });
  it("formats rates as percentages", () => {
    expect(formatPercent(0.1234, 1)).toBe("12.3%");
  });
});
