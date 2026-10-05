import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { PricingTable } from "@/components/marketing/pricing-table";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.pricing");
  return { title: t("title") };
}

export default async function PricingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing.pricing");
  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t("title")}</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">{t("intro")}</p>
      <div className="mt-8">
        <PricingTable />
      </div>
      <section className="mt-12 grid gap-6 md:grid-cols-2">
        <div>
          <h2 className="text-lg font-semibold">{t("trialTitle")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t("trialBody")}</p>
        </div>
        <div>
          <h2 className="text-lg font-semibold">{t("methodsTitle")}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{t("methodsBody")}</p>
        </div>
      </section>
    </div>
  );
}
