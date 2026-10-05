/**
 * Type aliases over the generated OpenAPI types (src/lib/api-types.ts).
 * Regenerate the source with `npm run gen:api` against a running backend.
 */
import type { components } from "./api-types";

type S = components["schemas"];

export type MeOut = S["MeOut"];
export type TokenOut = S["TokenOut"];
export type RegisterIn = S["RegisterIn"];
export type RegisterOut = S["RegisterOut"];
export type MeUpdateIn = S["MeUpdateIn"];
export type OkOut = S["OkOut"];

export type CountryOut = S["CountryOut"];
export type TierOut = S["TierOut"];
export type PlatformOut = S["PlatformOut"];
export type PlacementOut = S["PlacementOut"];
export type CategorySummaryOut = S["CategorySummaryOut"];
export type CategoryTemplateOut = S["CategoryTemplateOut"];
export type QuestionOut = S["QuestionOut"];
export type LocalAmountOut = S["LocalAmountOut"];

export type ProfileOut = S["ProfileOut"];
export type ProfileVersionOut = S["ProfileVersionOut"];
export type ProfileCreateIn = S["ProfileCreateIn"];
export type ProfileUpdateIn = S["ProfileUpdateIn"];
export type ProfileAttachIn = S["ProfileAttachIn"];
export type ProfileRefOut = S["ProfileRefOut"];

export type TestOut = S["TestOut"];
export type TestListItem = S["TestListItem"];
export type TestCreateIn = S["TestCreateIn"];
export type TestUpdateIn = S["TestUpdateIn"];
export type AudienceIn = S["AudienceIn"];
export type TargetingIn = S["TargetingIn"];
export type AdCopyIn = S["AdCopyIn"];
export type AssetOut = S["AssetOut"];
export type PlatformSelectionIn = S["PlatformSelectionIn"];
export type PlatformSelectionOut = S["PlatformSelectionOut"];
export type PostSettingsIn = S["PostSettingsIn"];
export type ScheduleIn = S["ScheduleIn"];
export type ConfirmOut = S["ConfirmOut"];
export type SpecCheckOut = S["SpecCheckOut"];
export type CancelOut = S["CancelOut"];
export type ProgressSnapshot = S["ProgressSnapshot"];
export type StreamTokenOut = S["StreamTokenOut"];
export type ReportOut = S["ReportOut"];
export type ReportPdfOut = S["ReportPdfOut"];
export type ReasonOut = S["ReasonOut"];
export type EvidenceOut = S["EvidenceOut"];
export type CommentOut = S["CommentOut"];
export type CompareOut = S["CompareOut"];

export type CheckoutOut = S["CheckoutOut"];
export type CheckoutTierOut = S["CheckoutTierOut"];
export type PaymentOut = S["PaymentOut"];
export type CardPaymentOut = S["CardPaymentOut"];
export type TrialPaymentOut = S["TrialPaymentOut"];
export type ManualPaymentOut = S["ManualPaymentOut"];

export type AdminPaymentOut = S["AdminPaymentOut"];
export type AdminTestListItem = S["AdminTestListItem"];
export type AdminTestOut = S["AdminTestOut"];
export type AdminUserOut = S["AdminUserOut"];
export type AdminUserPatchIn = S["AdminUserPatchIn"];
export type AdminMetricsOut = S["AdminMetricsOut"];
export type PricesOut = S["PricesOut"];
export type PricesIn = S["PricesIn"];
export type AppSettingsOut = S["AppSettingsOut"];
export type AppSettingsIn = S["AppSettingsIn"];
export type CountryAdminOut = S["CountryAdminOut"];
export type CountryUpsertIn = S["CountryUpsertIn"];
export type PlatformAdminOut = S["PlatformAdminOut"];
export type PlatformUpsertIn = S["PlatformUpsertIn"];
export type ScenarioOut = S["ScenarioOut"];
export type SettingsVersionOut = S["SettingsVersionOut"];
export type VersionedCreateIn = S["VersionedCreateIn"];
export type VersionedUpdateIn = S["VersionedUpdateIn"];
export type WeightsOut = S["WeightsOut"];
export type WeightsIn = S["WeightsIn"];
export type FxRateOut = S["FxRateOut"];
export type FxRatesIn = S["FxRatesIn"];
export type CategoryDraftAiIn = S["CategoryDraftAiIn"];
export type SandboxRunIn = S["SandboxRunIn"];
export type SandboxResultOut = S["SandboxResultOut"];
export type HealthOut = S["HealthOut"];

export type Page<T> = { items: T[]; next_cursor: string | null };

export type TestStatus = TestOut["status"];
export type PostType = TestOut["post_type"];
export type Goal = TestOut["goal"];
export type PaymentStatus = PaymentOut["status"];

export const POST_TYPES: PostType[] = ["paid", "boosted", "organic"];
export const GOALS: Goal[] = ["sales", "messages", "traffic", "awareness", "engagement"];
export const CTAS = [
  "learn_more",
  "shop_now",
  "send_message",
  "order_now",
  "sign_up",
  "book_now",
  "get_offer",
  "none",
] as const;
export type Cta = (typeof CTAS)[number];
