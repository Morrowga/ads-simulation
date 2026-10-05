"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { ThemeToggle } from "./theme-toggle";

export function PublicHeader() {
  const t = useTranslations("marketing.nav");
  const { token, ready } = useAuth();
  return (
    <header className="border-b border-border">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span
            className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold"
            aria-hidden
          >
            A
          </span>
          ADVAR
        </Link>
        <nav className="ml-4 hidden items-center gap-4 text-sm sm:flex" aria-label={t("main")}>
          <Link href="/how-it-works" className="text-muted-foreground hover:text-foreground">
            {t("howItWorks")}
          </Link>
          <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
            {t("pricing")}
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {ready && token ? (
            <Button asChild size="sm">
              <Link href="/dashboard">{t("dashboard")}</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link href="/login">{t("login")}</Link>
              </Button>
              <Button asChild size="sm">
                <Link href="/register">{t("register")}</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

export function PublicFooter() {
  const t = useTranslations("marketing.footer");
  return (
    <footer className="border-t border-border py-8 text-sm text-muted-foreground">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 sm:flex-row sm:items-center sm:justify-between">
        <p>{t("copyright", { year: new Date().getFullYear() })}</p>
        <nav className="flex gap-4" aria-label={t("legal")}>
          <Link href="/legal" className="hover:text-foreground">
            {t("terms")}
          </Link>
          <Link href="/legal#privacy" className="hover:text-foreground">
            {t("privacy")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
