import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.how");
  return { title: t("title") };
}

export default async function HowItWorksPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing.how");
  const sections = ["profile", "ad", "audience", "simulation", "report", "honesty"] as const;
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t("title")}</h1>
      <p className="mt-2 text-muted-foreground">{t("intro")}</p>
      <ol className="mt-10 space-y-8">
        {sections.map((s, i) => (
          <li key={s} className="flex gap-4">
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary tabular"
              aria-hidden
            >
              {i + 1}
            </span>
            <div>
              <h2 className="text-lg font-semibold">{t(`sections.${s}.title`)}</h2>
              <p className="mt-1 text-muted-foreground">{t(`sections.${s}.body`)}</p>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-12">
        <Button asChild size="lg">
          <Link href="/register">{t("cta")}</Link>
        </Button>
      </div>
    </div>
  );
}
