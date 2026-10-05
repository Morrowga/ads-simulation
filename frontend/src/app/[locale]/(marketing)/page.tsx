import { ArrowRight, Eye, MessageSquareText, ShieldCheck, Timer } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { PricingTable } from "@/components/marketing/pricing-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("marketing.home");
  const steps = ["upload", "audience", "watch", "reasons"] as const;
  const icons = { upload: Eye, audience: ShieldCheck, watch: Timer, reasons: MessageSquareText };
  return (
    <div className="mx-auto max-w-6xl px-4">
      <section className="py-16 sm:py-24">
        <div className="max-w-2xl">
          <p className="mb-3 text-sm font-medium text-primary">{t("eyebrow")}</p>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">{t("title")}</h1>
          <p className="mt-4 text-lg text-muted-foreground">{t("subtitle")}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/register">
                {t("cta")} <ArrowRight aria-hidden />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/how-it-works">{t("secondary")}</Link>
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">{t("ctaNote")}</p>
        </div>
      </section>

      <section className="py-12" aria-labelledby="how">
        <h2 id="how" className="text-2xl font-semibold tracking-tight">
          {t("howTitle")}
        </h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => {
            const Icon = icons[s];
            return (
              <Card key={s}>
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2 text-primary">
                    <Icon className="h-5 w-5" aria-hidden />
                    <span className="text-xs font-semibold uppercase tracking-wide">
                      {t("step", { n: i + 1 })}
                    </span>
                  </div>
                  <h3 className="font-medium">{t(`steps.${s}.title`)}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{t(`steps.${s}.body`)}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="py-12" aria-labelledby="sample">
        <h2 id="sample" className="text-2xl font-semibold tracking-tight">
          {t("sampleTitle")}
        </h2>
        <p className="mt-2 max-w-2xl text-muted-foreground">{t("sampleBody")}</p>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {(["score", "funnel", "comments"] as const).map((k) => (
            <Card key={k}>
              <CardContent className="p-5">
                <h3 className="font-medium">{t(`sample.${k}.title`)}</h3>
                <p className="mt-1 text-sm text-muted-foreground">{t(`sample.${k}.body`)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">{t("disclaimer")}</p>
      </section>

      <section className="py-12" aria-labelledby="pricing">
        <h2 id="pricing" className="text-2xl font-semibold tracking-tight">
          {t("pricingTitle")}
        </h2>
        <p className="mt-2 mb-6 text-muted-foreground">{t("pricingBody")}</p>
        <PricingTable compact />
      </section>

      <section className="my-12 rounded-xl border border-border bg-muted/40 p-8 text-center">
        <h2 className="text-2xl font-semibold tracking-tight">{t("finalTitle")}</h2>
        <p className="mt-2 text-muted-foreground">{t("finalBody")}</p>
        <Button asChild size="lg" className="mt-6">
          <Link href="/register">{t("cta")}</Link>
        </Button>
      </section>
    </div>
  );
}
