import { beforeEach, describe, expect, it } from "vitest";
import {
  clearDraft,
  defaultAd,
  emptyDraft,
  loadDraft,
  saveDraft,
  WIZARD_DRAFT_KEY,
} from "@/lib/wizard-draft";

describe("wizard draft storage", () => {
  beforeEach(() => window.localStorage.clear());
  it("round-trips a local draft", () => {
    saveDraft({ ...emptyDraft(), step: 1, ad: { ...defaultAd(), title: "My ad" } });
    const d = loadDraft();
    expect(d?.step).toBe(1);
    expect(d?.ad?.title).toBe("My ad");
    expect(window.localStorage.getItem(WIZARD_DRAFT_KEY)).not.toBeNull();
  });
  it("clears the draft", () => {
    saveDraft(emptyDraft());
    clearDraft();
    expect(loadDraft()).toBeNull();
  });
  it("ignores corrupt data", () => {
    window.localStorage.setItem(WIZARD_DRAFT_KEY, "{not json");
    expect(loadDraft()).toBeNull();
  });
});
