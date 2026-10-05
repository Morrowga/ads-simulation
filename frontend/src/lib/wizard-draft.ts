/**
 * Local wizard draft ("draft-then-create"): steps 0–2 are kept in localStorage until the target
 * country is known (Audience step), because POST /tests requires country_code. From then on the
 * server draft is the source of truth and this record only remembers which test is being edited.
 */
import type { AdStepValues, AudienceValues } from "./schemas";

export const WIZARD_DRAFT_KEY = "advar.wizard.draft.v1";

export interface ProfileChoice {
  profile_id: string;
  mode: "preset" | "one_time" | "update_preset" | "new_preset";
  changes: Record<string, unknown>;
  new_preset_name?: string | null;
}

export interface WizardDraft {
  version: 1;
  updated_at: string;
  test_id: string | null;
  step: number;
  profile: ProfileChoice | null;
  ad: AdStepValues | null;
  country_code: string | null;
  audiences: AudienceValues[] | null;
  tier_code: string;
}

export const emptyDraft = (): WizardDraft => ({
  version: 1,
  updated_at: new Date().toISOString(),
  test_id: null,
  step: 0,
  profile: null,
  ad: null,
  country_code: null,
  audiences: null,
  tier_code: "standard",
});

export function loadDraft(): WizardDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(WIZARD_DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as WizardDraft;
    return parsed.version === 1 ? parsed : null;
  } catch {
    return null;
  }
}

export function saveDraft(draft: WizardDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      WIZARD_DRAFT_KEY,
      JSON.stringify({ ...draft, updated_at: new Date().toISOString() }),
    );
  } catch {
    // storage full or blocked: the wizard still works within the session
  }
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(WIZARD_DRAFT_KEY);
  } catch {
    // ignore
  }
}

export const defaultAd = (): AdStepValues => ({
  title: "",
  caption: "",
  headline: "",
  cta: "learn_more",
  link_url: "",
});

export const defaultAudience = (name = "Main audience", languages: string[] = []): AudienceValues => ({
  name,
  kind: "targeted",
  targeting: {
    age_min: 18,
    age_max: 55,
    genders: ["f", "m", "other"],
    interests: [],
    location: "",
    radius_km: null,
    languages,
    audience_size: null,
  },
});
