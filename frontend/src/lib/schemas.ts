/** zod schemas shared by forms. Messages are translation keys (resolved by the form field component). */
import { z } from "zod";

export const emailSchema = z.string().trim().min(1, "required").email("email");
export const passwordSchema = z.string().min(8, "password_min");

export const loginSchema = z.object({ email: emailSchema, password: z.string().min(1, "required") });
export type LoginValues = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    name: z.string().trim().min(1, "required").max(120, "too_long"),
    email: emailSchema,
    password: passwordSchema,
    confirm: z.string(),
    country: z.string().optional(),
    terms: z.literal(true, { errorMap: () => ({ message: "terms" }) }),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "password_match" });
export type RegisterValues = z.infer<typeof registerSchema>;

export const forgotSchema = z.object({ email: emailSchema });
export const resetSchema = z
  .object({ password: passwordSchema, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "password_match" });

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "required"),
    new_password: passwordSchema,
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "password_match" });

export const profileMetaSchema = z.object({
  name: z.string().trim().min(1, "required").max(120, "too_long"),
  category_code: z.string().min(1, "required"),
  is_default: z.boolean(),
});
export type ProfileMetaValues = z.infer<typeof profileMetaSchema>;

export const profileEditMetaSchema = profileMetaSchema.extend({
  category_code: z.string(),
});

// ---------------------------------------------------------------- wizard
export const adStepSchema = z.object({
  title: z.string().trim().min(1, "required").max(160, "too_long"),
  caption: z.string().max(2200, "caption_max"),
  headline: z.string().max(200, "too_long"),
  cta: z.string().min(1, "required"),
  link_url: z.string().trim().max(500, "too_long").optional().or(z.literal("")),
});
export type AdStepValues = z.infer<typeof adStepSchema>;

export const targetingSchema = z
  .object({
    age_min: z.number().int().min(13).max(80),
    age_max: z.number().int().min(13).max(99),
    genders: z.array(z.string()).min(1, "gender_required"),
    interests: z.array(z.string()),
    location: z.string().trim().min(1, "location_required").max(120, "too_long"),
    radius_km: z.number().min(0).max(500).nullable(),
    languages: z.array(z.string()),
    audience_size: z.number().int().min(100).nullable(),
  })
  .refine((v) => v.age_max >= v.age_min, { path: ["age_max"], message: "age_range" });

export const audienceSchema = z.object({
  name: z.string().trim().min(1, "required").max(80, "too_long"),
  kind: z.enum(["targeted", "followers", "custom"]),
  targeting: targetingSchema,
});
export type AudienceValues = z.infer<typeof audienceSchema>;

export const audienceStepSchema = z.object({
  country_code: z.string().length(2, "required"),
  audiences: z.array(audienceSchema).min(1).max(3),
});
export type AudienceStepValues = z.infer<typeof audienceStepSchema>;

export const platformSelectionSchema = z.object({
  code: z.string(),
  placements: z.array(z.string()).min(1, "placement_required"),
  /** percent 0–100 (backend convention) */
  budget_share: z.number().min(0).max(100),
});

export const platformsStepSchema = z
  .object({
    post_type: z.enum(["paid", "boosted", "organic"]),
    goal: z.enum(["sales", "messages", "traffic", "awareness", "engagement"]),
    platforms: z.array(platformSelectionSchema).min(1, "platform_required").max(3),
    budget: z.number().min(0).nullable(),
    currency: z.string().length(3),
    start_date: z.string().optional().or(z.literal("")),
    days: z.number().int().min(1).max(14),
    post_at: z.string().optional().or(z.literal("")),
    observe_days: z.number().int().min(1).max(7),
    tier_code: z.string().min(1),
  })
  .superRefine((v, ctx) => {
    const total = v.platforms.reduce((s, p) => s + p.budget_share, 0);
    if (v.platforms.length > 1 && Math.abs(total - 100) > 0.011) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["platforms"], message: "shares_total" });
    }
    if (v.post_type !== "organic") {
      if (v.budget === null || v.budget <= 0)
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["budget"], message: "budget_required" });
      if (!v.start_date)
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["start_date"], message: "required" });
      else if (new Date(v.start_date) < new Date(new Date().toDateString()))
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["start_date"], message: "start_future" });
    } else if (!v.post_at) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["post_at"], message: "required" });
    }
  });
export type PlatformsStepValues = z.infer<typeof platformsStepSchema>;

// ---------------------------------------------------------------- media checks (client-side; server re-checks)
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_VIDEO_BYTES = 50 * 1024 * 1024;
export const MAX_VIDEO_SECONDS = 60;
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const VIDEO_TYPES = ["video/mp4", "video/quicktime"];
