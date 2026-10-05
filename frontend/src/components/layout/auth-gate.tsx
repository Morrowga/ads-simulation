"use client";

import { useTranslations } from "next-intl";
import { useEffect, type ReactNode } from "react";
import { AppShellSkeleton } from "@/components/layout/loading";
import { usePathname, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";

/** Client-side guard for (app) and (admin) routes; the API enforces the real rules. */
export function AuthGate({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { ready, token, me, isAdmin } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("common");

  useEffect(() => {
    if (ready && !token) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [ready, token, router, pathname]);

  useEffect(() => {
    if (admin && me && !isAdmin) router.replace("/dashboard");
  }, [admin, me, isAdmin, router]);

  if (!ready || !token || (admin && !me)) {
    return (
      <>
        <AppShellSkeleton />
        <p className="sr-only">{t("loading")}</p>
      </>
    );
  }
  if (admin && !isAdmin) return null;
  return <>{children}</>;
}