"use client";

import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Money } from "@/components/layout/money";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { useCountries, useTiers } from "@/lib/queries";
import { cn } from "@/lib/utils";

export function PricingTable({ compact = false }: { compact?: boolean }) {
  const t = useTranslations("marketing.pricing");
  const countries = useCountries();
  const [country, setCountry] = useState<string>("");
  const tiers = useTiers(country || null, 1);

  return (
    <div className="space-y-6">
      {!compact ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground">{t("localHint")}</p>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="sm:w-56" aria-label={t("countryLabel")}>
              <SelectValue placeholder={t("countryPlaceholder")} />
            </SelectTrigger>
            <SelectContent>
              {(countries.data ?? []).map((c) => (
                <SelectItem key={c.code} value={c.code}>
                  {c.name} · {c.currency}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        {tiers.isLoading
          ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-64" />)
          : (tiers.data ?? []).map((tier) => {
              const recommended = tier.code === "standard";
              return (
                <Card
                  key={tier.code}
                  className={cn("relative flex flex-col", recommended && "border-primary shadow-sm")}
                >
                  {recommended ? (
                    <Badge className="absolute -top-2.5 left-4">{t("recommended")}</Badge>
                  ) : null}
                  <CardHeader>
                    <CardTitle>{tier.name}</CardTitle>
                    <CardDescription>{t(`tiers.${tier.code}` as never)}</CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-1 flex-col gap-4">
                    <div>
                      <p className="text-3xl font-semibold">
                        <Money display={tier.price_display} local={tier.local} />
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {t("extraPlatform", { price: tier.extra_platform_display })}
                      </p>
                    </div>
                    <ul className="space-y-2 text-sm">
                      <li className="flex gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />{" "}
                        {t("runs", { count: tier.runs_target })}
                      </li>
                      <li className="flex gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />{" "}
                        {t("scenarios", { count: tier.scenarios })}
                      </li>
                      <li className="flex gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />{" "}
                        {t("agents", { count: tier.agents, archetypes: tier.archetypes })}
                      </li>
                      <li className="flex gap-2">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />{" "}
                        {t("audiences", { count: tier.max_audiences })}
                      </li>
                    </ul>
                    <Button asChild variant={recommended ? "default" : "outline"} className="mt-auto">
                      <Link href="/register">{t("start")}</Link>
                    </Button>
                  </CardContent>
                </Card>
              );
            })}
      </div>
      {tiers.isError ? <p className="text-sm text-muted-foreground">{t("unavailable")}</p> : null}
    </div>
  );
}
