import { defineRouting } from "next-intl/routing";

export const locales = ["en", "th"] as const;
export type Locale = (typeof locales)[number];

export const routing = defineRouting({
  locales,
  defaultLocale: (process.env.NEXT_PUBLIC_DEFAULT_LOCALE as Locale | undefined) ?? "en",
  localePrefix: "always",
});
