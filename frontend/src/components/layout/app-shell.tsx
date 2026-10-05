"use client";

import {
  BarChart3,
  Building2,
  CreditCard,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  LogOut,
  Menu,
  Percent,
  Settings,
  Shapes,
  ShieldCheck,
  Sliders,
  Tags,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { useAdminMetrics } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";

interface NavItem {
  href: string;
  key: string;
  icon: typeof LayoutDashboard;
  badge?: number;
}

function NavLink({ item, onClick }: { item: NavItem; onClick?: () => void }) {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const active =
    pathname === item.href ||
    (item.href !== "/admin" && pathname.startsWith(`${item.href}/`)) ||
    (item.href === "/tests" && pathname.startsWith("/tests"));
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors touch-target",
        active ? "bg-primary/10 text-primary" : "text-foreground/80 hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden />
      <span className="flex-1">{t(item.key)}</span>
      {item.badge ? (
        <Badge variant="warning" aria-label={t("pendingOrders", { count: item.badge })}>
          {item.badge}
        </Badge>
      ) : null}
    </Link>
  );
}

function AdminBadgeNav({ onClick }: { onClick?: () => void }) {
  const t = useTranslations("nav");
  const metrics = useAdminMetrics(30);
  const pending = metrics.data?.pending_manual_orders ?? 0;
  const items: NavItem[] = [
    { href: "/admin", key: "adminOverview", icon: BarChart3 },
    { href: "/admin/payments", key: "adminPayments", icon: Wallet, badge: pending },
    { href: "/admin/tests", key: "adminTests", icon: FlaskConical },
    { href: "/admin/users", key: "adminUsers", icon: Users },
    { href: "/admin/prices", key: "adminPrices", icon: Percent },
    { href: "/admin/settings", key: "adminSettings", icon: Sliders },
    { href: "/admin/countries", key: "adminCountries", icon: Globe2 },
    { href: "/admin/categories", key: "adminCategories", icon: Tags },
    { href: "/admin/platforms", key: "adminPlatforms", icon: Shapes },
    { href: "/admin/scenarios", key: "adminScenarios", icon: FlaskConical },
    { href: "/admin/weights", key: "adminWeights", icon: Sliders },
    { href: "/admin/fx-rates", key: "adminFx", icon: CreditCard },
  ];
  return (
    <div className="mt-6">
      <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t("admin")}
      </p>
      <nav aria-label={t("admin")} className="space-y-0.5">
        {items.map((i) => (
          <NavLink key={i.href} item={i} onClick={onClick} />
        ))}
      </nav>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const { me, isAdmin, logout } = useAuth();
  const router = useRouter();
  const locale = useLocale();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);

  const userItems: NavItem[] = [
    { href: "/dashboard", key: "dashboard", icon: LayoutDashboard },
    { href: "/profiles", key: "profiles", icon: Building2 },
    { href: "/payments", key: "payments", icon: CreditCard },
    { href: "/settings", key: "settings", icon: Settings },
  ];

  const sidebar = (onClick?: () => void) => (
    <>
      <nav aria-label={t("main")} className="space-y-0.5">
        {userItems.map((i) => (
          <NavLink key={i.href} item={i} onClick={onClick} />
        ))}
      </nav>
      {isAdmin ? <AdminBadgeNav onClick={onClick} /> : null}
    </>
  );

  const onLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <div className="min-h-dvh bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-screen-2xl items-center gap-3 px-4">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden touch-target"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? tc("closeMenu") : tc("openMenu")}
          >
            {open ? <X aria-hidden /> : <Menu aria-hidden />}
          </Button>
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold tracking-tight">
            <span
              className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold"
              aria-hidden
            >
              A
            </span>
            ADVAR
          </Link>
          <div className="ml-auto flex items-center gap-1">
            <Button asChild size="sm" className="hidden sm:inline-flex">
              <Link href="/tests/new">{t("newTest")}</Link>
            </Button>
            <ThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="touch-target max-w-[12rem]">
                  <span className="truncate">{me?.name || me?.email || "…"}</span>
                  {isAdmin ? <ShieldCheck className="text-primary" aria-label={t("admin")} /> : null}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
                  {me?.email}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/settings")}>
                  <Settings aria-hidden /> {t("settings")}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={() => router.replace(pathname, { locale: locale === "en" ? "th" : "en" })}
                >
                  <Globe2 aria-hidden /> {locale === "en" ? "ไทย" : "English"}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={onLogout}>
                  <LogOut aria-hidden /> {t("logout")}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-screen-2xl">
        <aside className="hidden w-60 shrink-0 border-r border-border p-4 lg:block lg:sticky lg:top-14 lg:h-[calc(100dvh-3.5rem)] lg:overflow-y-auto">
          {sidebar()}
        </aside>
        {open ? (
          <div
            id="mobile-nav"
            className="fixed inset-x-0 top-14 bottom-0 z-30 overflow-y-auto border-t border-border bg-background p-4 lg:hidden"
          >
            <Button asChild className="mb-4 w-full">
              <Link href="/tests/new">{t("newTest")}</Link>
            </Button>
            {sidebar(() => setOpen(false))}
          </div>
        ) : null}
        <main id="main" className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
