import createMiddleware from "next-intl/middleware";
import { NextResponse, type NextRequest } from "next/server";
import { routing } from "./i18n/routing";

const intl = createMiddleware(routing);

// Routes that need a signed-in user (UX redirect only; the API enforces the real rules).
const PROTECTED = ["/dashboard", "/profiles", "/tests", "/payments", "/settings", "/admin"];
export const AUTH_HINT_COOKIE = "advar_auth";

function stripLocale(pathname: string): string {
  const parts = pathname.split("/");
  if (parts.length > 1 && (routing.locales as readonly string[]).includes(parts[1] ?? "")) {
    return "/" + parts.slice(2).join("/");
  }
  return pathname;
}

export default function middleware(request: NextRequest) {
  const path = stripLocale(request.nextUrl.pathname);
  const needsAuth = PROTECTED.some((p) => path === p || path.startsWith(p + "/"));
  const loggedIn = request.cookies.get(AUTH_HINT_COOKIE)?.value === "1";
  if (needsAuth && !loggedIn) {
    const localeMatch = request.nextUrl.pathname.split("/")[1];
    const locale = (routing.locales as readonly string[]).includes(localeMatch ?? "")
      ? localeMatch
      : routing.defaultLocale;
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}/login`;
    url.search = `?next=${encodeURIComponent(path + request.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }
  return intl(request);
}

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
