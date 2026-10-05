import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("marketing.legal");
  return { title: t("title") };
}

export default async function LegalPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing.legal");
  const terms = ["service", "simulation", "payments", "cancel", "accounts"] as const;
  const privacy = ["data", "media", "payments", "retention", "contact"] as const;
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">{t("title")}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("updated")}</p>
      <section id="terms" className="mt-10 space-y-4">
        <h2 className="text-xl font-semibold">{t("termsTitle")}</h2>
        {terms.map((k) => (
          <div key={k}>
            <h3 className="font-medium">{t(`terms.${k}.title`)}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{t(`terms.${k}.body`)}</p>
          </div>
        ))}
      </section>
      <section id="privacy" className="mt-12 space-y-4">
        <h2 className="text-xl font-semibold">{t("privacyTitle")}</h2>
        {privacy.map((k) => (
          <div key={k}>
            <h3 className="font-medium">{t(`privacy.${k}.title`)}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{t(`privacy.${k}.body`)}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
