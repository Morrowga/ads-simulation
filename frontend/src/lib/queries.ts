"use client";

/** TanStack Query hooks for every endpoint the UI uses. Keys follow the spec (section 11). */
import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import { del, get, patch, post, put } from "./api";
import type {
  AdminMetricsOut,
  AdminPaymentOut,
  AdminTestListItem,
  AdminTestOut,
  AdminUserOut,
  AdminUserPatchIn,
  AppSettingsOut,
  CancelOut,
  CardPaymentOut,
  CategorySummaryOut,
  CategoryTemplateOut,
  CheckoutOut,
  CompareOut,
  ConfirmOut,
  CountryAdminOut,
  CountryOut,
  CountryUpsertIn,
  FxRateOut,
  FxRatesIn,
  ManualPaymentOut,
  Page,
  PaymentOut,
  PlatformAdminOut,
  PlatformOut,
  PlatformSelectionIn,
  PlatformUpsertIn,
  PostSettingsIn,
  PricesIn,
  PricesOut,
  ProfileAttachIn,
  ProfileCreateIn,
  ProfileOut,
  ProfileRefOut,
  ProfileUpdateIn,
  ProfileVersionOut,
  ProgressSnapshot,
  ReportOut,
  ReportPdfOut,
  SandboxResultOut,
  SandboxRunIn,
  ScenarioOut,
  SettingsVersionOut,
  TestCreateIn,
  TestListItem,
  TestOut,
  TestUpdateIn,
  TierOut,
  TrialPaymentOut,
  VersionedCreateIn,
  VersionedUpdateIn,
  WeightsIn,
  WeightsOut,
} from "./types";

type Opts<T> = Omit<UseQueryOptions<T>, "queryKey" | "queryFn">;

// ------------------------------------------------------------------ config
export const useCountries = () =>
  useQuery({
    queryKey: ["countries"],
    queryFn: () => get<CountryOut[]>("/countries"),
    staleTime: 5 * 60_000,
  });
export const useTiers = (country?: string | null, platforms = 1) =>
  useQuery({
    queryKey: ["tiers", country ?? null, platforms],
    queryFn: () => get<TierOut[]>("/tiers", { country: country ?? undefined, platforms }),
    staleTime: 5 * 60_000,
  });
export const usePlatforms = () =>
  useQuery({
    queryKey: ["platforms"],
    queryFn: () => get<PlatformOut[]>("/platforms"),
    staleTime: 5 * 60_000,
  });
export const useCategories = () =>
  useQuery({
    queryKey: ["categories"],
    queryFn: () => get<CategorySummaryOut[]>("/categories"),
    staleTime: 5 * 60_000,
  });
export const useCategory = (code: string | null | undefined) =>
  useQuery({
    queryKey: ["category", code],
    queryFn: () => get<CategoryTemplateOut>(`/categories/${code}`),
    enabled: !!code,
    staleTime: 5 * 60_000,
  });

// ------------------------------------------------------------------ profiles
export const useProfiles = () =>
  useQuery({ queryKey: ["profiles"], queryFn: () => get<ProfileOut[]>("/profiles") });
export const useProfile = (id: string | null | undefined) =>
  useQuery({ queryKey: ["profile", id], queryFn: () => get<ProfileOut>(`/profiles/${id}`), enabled: !!id });
export const useProfileVersions = (id: string | null | undefined, opts: Opts<ProfileVersionOut[]> = {}) =>
  useQuery({
    queryKey: ["profile", id, "versions"],
    queryFn: () => get<ProfileVersionOut[]>(`/profiles/${id}/versions`),
    enabled: !!id,
    ...opts,
  });

export function useProfileMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["profiles"] });
  return {
    create: useMutation({
      mutationFn: (body: ProfileCreateIn) => post<ProfileOut>("/profiles", body),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, body }: { id: string; body: ProfileUpdateIn }) =>
        put<ProfileOut>(`/profiles/${id}`, body),
      onSuccess: (_d, v) => {
        invalidate();
        qc.invalidateQueries({ queryKey: ["profile", v.id] });
      },
    }),
    duplicate: useMutation({
      mutationFn: ({ id, name }: { id: string; name?: string }) =>
        post<ProfileOut>(`/profiles/${id}/duplicate`, { name: name ?? null }),
      onSuccess: invalidate,
    }),
    archive: useMutation({
      mutationFn: (id: string) => del<{ ok: boolean }>(`/profiles/${id}`),
      onSuccess: invalidate,
    }),
  };
}

// ------------------------------------------------------------------ tests
export const useTests = (cursor: string | null = null, status?: string, limit = 20) =>
  useQuery({
    queryKey: ["tests", cursor, status ?? null, limit],
    queryFn: () => get<Page<TestListItem>>("/tests", { cursor, status, limit }),
    // while any test is queued/running, keep the list fresh so progress and status never stick
    refetchInterval: (query) => {
      const items = ((query.state.data as { items?: { status?: string }[] } | undefined)?.items ?? []);
      const active = items.some((t) => t.status === "queued" || t.status === "running");
      return active ? 3000 : false;
    },
    refetchOnMount: "always",
  });
export const useTest = (id: string | null | undefined, opts: Opts<TestOut> = {}) =>
  useQuery({ queryKey: ["test", id], queryFn: () => get<TestOut>(`/tests/${id}`), enabled: !!id, ...opts });
export const useProgressSnapshot = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["test", id, "snapshot"],
    queryFn: () => get<ProgressSnapshot>(`/tests/${id}/progress/snapshot`),
    enabled: !!id,
    staleTime: 0,
  });
export const useReport = (id: string | null | undefined, opts: Opts<ReportOut> = {}) =>
  useQuery({
    queryKey: ["report", id],
    queryFn: () => get<ReportOut>(`/tests/${id}/report`),
    enabled: !!id,
    ...opts,
  });
export const useCompare = (a: string | null, b: string | null) =>
  useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => get<CompareOut>("/tests/compare", { a, b }),
    enabled: !!a && !!b,
  });
export const useCheckout = (id: string | null | undefined, opts: Opts<CheckoutOut> = {}) =>
  useQuery({
    queryKey: ["checkout", id],
    queryFn: () => get<CheckoutOut>(`/tests/${id}/checkout`),
    enabled: !!id,
    ...opts,
  });

export function useTestMutations(id?: string) {
  const qc = useQueryClient();
  const invalidateTest = (testId: string) => {
    qc.invalidateQueries({ queryKey: ["test", testId] });
    qc.invalidateQueries({ queryKey: ["tests"] });
    qc.invalidateQueries({ queryKey: ["checkout", testId] });
  };
  return {
    create: useMutation({
      mutationFn: (body: TestCreateIn) => post<TestOut>("/tests", body),
      onSuccess: () => qc.invalidateQueries({ queryKey: ["tests"] }),
    }),
    update: useMutation({
      mutationFn: ({ testId, body }: { testId: string; body: TestUpdateIn }) =>
        patch<TestOut>(`/tests/${testId}`, body),
      onSuccess: (_d, v) => invalidateTest(v.testId),
    }),
    remove: useMutation({
      mutationFn: (testId: string) => del<{ ok: boolean }>(`/tests/${testId}`),
      onSuccess: () => qc.invalidateQueries({ queryKey: ["tests"] }),
    }),
    setProfile: useMutation({
      mutationFn: ({ testId, body }: { testId: string; body: ProfileAttachIn }) =>
        put<ProfileRefOut>(`/tests/${testId}/profile`, body),
      onSuccess: (_d, v) => {
        invalidateTest(v.testId);
        qc.invalidateQueries({ queryKey: ["profiles"] });
      },
    }),
    setPlatforms: useMutation({
      mutationFn: ({ testId, body }: { testId: string; body: PlatformSelectionIn[] }) =>
        put<TestOut>(`/tests/${testId}/platforms`, body),
      onSuccess: (_d, v) => invalidateTest(v.testId),
    }),
    setPost: useMutation({
      mutationFn: ({ testId, body }: { testId: string; body: PostSettingsIn }) =>
        put<TestOut>(`/tests/${testId}/post`, body),
      onSuccess: (_d, v) => invalidateTest(v.testId),
    }),
    deleteAsset: useMutation({
      mutationFn: ({ testId, assetId }: { testId: string; assetId: string }) =>
        del<{ ok: boolean }>(`/tests/${testId}/assets/${assetId}`),
      onSuccess: (_d, v) => invalidateTest(v.testId),
    }),
    confirm: useMutation({
      mutationFn: (testId: string) => post<ConfirmOut>(`/tests/${testId}/confirm`),
      onSuccess: (_d, testId) => invalidateTest(testId),
    }),
    cancel: useMutation({
      mutationFn: (testId: string) => post<CancelOut>(`/tests/${testId}/cancel`),
      onSuccess: (_d, testId) => invalidateTest(testId),
    }),
    restart: useMutation({
      mutationFn: (testId: string) => post<TestOut>(`/tests/${testId}/restart`),
      onSuccess: (_d, testId) => invalidateTest(testId),
    }),
    duplicate: useMutation({
      mutationFn: (testId: string) => post<TestOut>(`/tests/${testId}/duplicate`),
      onSuccess: () => qc.invalidateQueries({ queryKey: ["tests"] }),
    }),
    payTrial: useMutation({
      mutationFn: (testId: string) => post<TrialPaymentOut>(`/tests/${testId}/pay/trial`),
      onSuccess: (_d, testId) => {
        invalidateTest(testId);
        qc.invalidateQueries({ queryKey: ["me"] });
      },
    }),
    payCard: useMutation({
      mutationFn: (testId: string) => post<CardPaymentOut>(`/tests/${testId}/pay/card`),
      onSuccess: (_d, testId) => invalidateTest(testId),
    }),
    payManual: useMutation({
      mutationFn: (testId: string) => post<ManualPaymentOut>(`/tests/${testId}/pay/manual`),
      onSuccess: (_d, testId) => {
        invalidateTest(testId);
        qc.invalidateQueries({ queryKey: ["payments"] });
      },
    }),
    reportPdf: useMutation({
      mutationFn: (testId: string) => get<ReportPdfOut>(`/tests/${testId}/report.pdf`),
    }),
    invalidate: () => id && invalidateTest(id),
  };
}

// ------------------------------------------------------------------ payments
export const usePayments = (cursor: string | null = null) =>
  useQuery({
    queryKey: ["payments", cursor],
    queryFn: () => get<Page<PaymentOut>>("/payments", { cursor, limit: 50 }),
  });

// ------------------------------------------------------------------ admin
export const useAdminMetrics = (days = 30) =>
  useQuery({
    queryKey: ["admin", "metrics", days],
    queryFn: () => get<AdminMetricsOut>("/admin/metrics", { days }),
  });
export const useAdminPayments = (status: string | null, code: string | null, cursor: string | null = null) =>
  useQuery({
    queryKey: ["admin", "payments", status ?? null, code ?? null, cursor],
    queryFn: () => get<Page<AdminPaymentOut>>("/admin/payments", { status, code, cursor, limit: 50 }),
  });
export const useAdminTests = (
  status: string | null,
  userEmail: string | null,
  cursor: string | null = null,
) =>
  useQuery({
    queryKey: ["admin", "tests", status ?? null, userEmail ?? null, cursor],
    queryFn: () =>
      get<Page<AdminTestListItem>>("/admin/tests", { status, user_email: userEmail, cursor, limit: 50 }),
  });
export const useAdminTest = (id: string | null | undefined) =>
  useQuery({
    queryKey: ["admin", "test", id],
    queryFn: () => get<AdminTestOut>(`/admin/tests/${id}`),
    enabled: !!id,
  });
export const useAdminUsers = (q: string | null, cursor: string | null = null) =>
  useQuery({
    queryKey: ["admin", "users", q ?? null, cursor],
    queryFn: () => get<Page<AdminUserOut>>("/admin/users", { q, cursor, limit: 50 }),
  });
export const useAdminPrices = () =>
  useQuery({ queryKey: ["admin", "prices"], queryFn: () => get<PricesOut>("/admin/prices") });
export const useAdminSettings = () =>
  useQuery({ queryKey: ["admin", "settings"], queryFn: () => get<AppSettingsOut>("/admin/settings") });
export const useAdminCountries = () =>
  useQuery({ queryKey: ["admin", "countries"], queryFn: () => get<CountryAdminOut[]>("/admin/countries") });
export const useAdminCountryVersions = (code: string | null) =>
  useQuery({
    queryKey: ["admin", "countries", code, "versions"],
    queryFn: () => get<SettingsVersionOut[]>(`/admin/countries/${code}/versions`),
    enabled: !!code,
  });
export const useAdminCategories = () =>
  useQuery({
    queryKey: ["admin", "categories"],
    queryFn: () => get<SettingsVersionOut[]>("/admin/categories", { with_data: true }),
  });
export const useAdminPlatforms = () =>
  useQuery({ queryKey: ["admin", "platforms"], queryFn: () => get<PlatformAdminOut[]>("/admin/platforms") });
export const useAdminPlatformVersions = (code: string | null) =>
  useQuery({
    queryKey: ["admin", "platforms", code, "versions"],
    queryFn: () => get<SettingsVersionOut[]>(`/admin/platforms/${code}/versions`),
    enabled: !!code,
  });
export const useAdminScenarios = () =>
  useQuery({ queryKey: ["admin", "scenarios"], queryFn: () => get<ScenarioOut[]>("/admin/scenarios") });
export const useAdminWeights = () =>
  useQuery({ queryKey: ["admin", "weights"], queryFn: () => get<WeightsOut>("/admin/weights") });
export const useAdminFxRates = () =>
  useQuery({ queryKey: ["admin", "fx-rates"], queryFn: () => get<FxRateOut[]>("/admin/fx-rates") });

export function useAdminMutations() {
  const qc = useQueryClient();
  const inv = (...keys: string[]) => qc.invalidateQueries({ queryKey: ["admin", ...keys] });
  return {
    approve: useMutation({
      mutationFn: ({ id, reference }: { id: string; reference?: string }) =>
        post<AdminPaymentOut>(`/admin/payments/${id}/approve`, { admin_reference: reference || null }),
      onSuccess: () => {
        inv("payments");
        inv("metrics");
      },
    }),
    cancelOrder: useMutation({
      mutationFn: ({ id, reason }: { id: string; reason: string }) =>
        post<AdminPaymentOut>(`/admin/payments/${id}/cancel`, { reason }),
      onSuccess: () => {
        inv("payments");
        inv("metrics");
      },
    }),
    refund: useMutation({
      mutationFn: ({ id, reason, reference }: { id: string; reason: string; reference?: string }) =>
        post<AdminPaymentOut>(`/admin/payments/${id}/refund`, {
          reason,
          manual_refund_reference: reference || null,
        }),
      onSuccess: () => {
        inv("payments");
        inv("tests");
      },
    }),
    rerun: useMutation({
      mutationFn: (id: string) => post<AdminTestOut>(`/admin/tests/${id}/rerun`),
      onSuccess: (_d, id) => {
        inv("tests");
        inv("test", id);
      },
    }),
    patchUser: useMutation({
      mutationFn: ({ id, body }: { id: string; body: AdminUserPatchIn }) =>
        patch<AdminUserOut>(`/admin/users/${id}`, body),
      onSuccess: () => inv("users"),
    }),
    putPrices: useMutation({
      mutationFn: (body: PricesIn) => put<PricesOut>("/admin/prices", body),
      onSuccess: () => {
        inv("prices");
        qc.invalidateQueries({ queryKey: ["tiers"] });
      },
    }),
    putSettings: useMutation({
      mutationFn: (body: { values: Record<string, unknown>; change_note: string }) =>
        put<AppSettingsOut>("/admin/settings", body),
      onSuccess: () => inv("settings"),
    }),
    createCountry: useMutation({
      mutationFn: (body: CountryUpsertIn) => post<SettingsVersionOut>("/admin/countries", body),
      onSuccess: () => inv("countries"),
    }),
    updateCountry: useMutation({
      mutationFn: ({ code, body }: { code: string; body: VersionedUpdateIn }) =>
        put<SettingsVersionOut>(`/admin/countries/${code}`, body),
      onSuccess: () => inv("countries"),
    }),
    createCategory: useMutation({
      mutationFn: (body: VersionedCreateIn) => post<SettingsVersionOut>("/admin/categories", body),
      onSuccess: () => inv("categories"),
    }),
    updateCategory: useMutation({
      mutationFn: ({ code, body }: { code: string; body: VersionedUpdateIn }) =>
        put<SettingsVersionOut>(`/admin/categories/${code}`, body),
      onSuccess: () => inv("categories"),
    }),
    draftCategoryAi: useMutation({
      mutationFn: (body: {
        name: string;
        code?: string | null;
        parent_code?: string | null;
        hints?: string;
      }) => post<SettingsVersionOut>("/admin/categories/draft-ai", body),
      onSuccess: () => inv("categories"),
    }),
    putPlatform: useMutation({
      mutationFn: ({ code, body }: { code: string; body: PlatformUpsertIn }) =>
        put<PlatformAdminOut>(`/admin/platforms/${code}`, body),
      onSuccess: () => {
        inv("platforms");
        qc.invalidateQueries({ queryKey: ["platforms"] });
      },
    }),
    createScenario: useMutation({
      mutationFn: (body: VersionedCreateIn) => post<SettingsVersionOut>("/admin/scenarios", body),
      onSuccess: () => inv("scenarios"),
    }),
    updateScenario: useMutation({
      mutationFn: ({ id, body }: { id: string; body: VersionedUpdateIn }) =>
        put<SettingsVersionOut>(`/admin/scenarios/${id}`, body),
      onSuccess: () => inv("scenarios"),
    }),
    putWeights: useMutation({
      mutationFn: (body: WeightsIn) => put<WeightsOut>("/admin/weights", body),
      onSuccess: () => inv("weights"),
    }),
    putFxRates: useMutation({
      mutationFn: (body: FxRatesIn) => put<FxRateOut[]>("/admin/fx-rates", body),
      onSuccess: () => {
        inv("fx-rates");
        qc.invalidateQueries({ queryKey: ["tiers"] });
      },
    }),
    publish: useMutation({
      mutationFn: ({ kind, id, note }: { kind: string; id: string; note: string }) =>
        post<SettingsVersionOut>(`/admin/settings/${kind}/${id}/publish`, { change_note: note }),
      onSuccess: (_d, v) => {
        inv(v.kind);
        qc.invalidateQueries({ queryKey: [v.kind] });
        qc.invalidateQueries({ queryKey: ["category"] });
      },
    }),
    rollback: useMutation({
      mutationFn: ({
        kind,
        id,
        toVersion,
        note,
      }: {
        kind: string;
        id: string;
        toVersion?: number;
        note: string;
      }) =>
        post<SettingsVersionOut>(`/admin/settings/${kind}/${id}/rollback`, {
          to_version: toVersion ?? null,
          change_note: note,
        }),
      onSuccess: (_d, v) => {
        inv(v.kind);
        qc.invalidateQueries({ queryKey: [v.kind] });
      },
    }),
    sandbox: useMutation({
      mutationFn: (body: Partial<SandboxRunIn>) => post<SandboxResultOut>("/admin/sandbox/run", body),
    }),
  };
}
