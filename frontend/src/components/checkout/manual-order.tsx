"use client";

/** Myanmar manual payment order: MMK amount, our accounts, payment code, social links, expiry countdown. */
import { Clock, ExternalLink } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { CopyButton } from "@/components/layout/copy-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCountdown, useCountdown } from "@/hooks/use-countdown";
import { formatDateTime, formatMoney, titleCase } from "@/lib/format";
import type { ManualPaymentOut, PaymentOut } from "@/lib/types";

const MANUAL_KEY = (testId: string) => `advar.manual.${testId}`;

export function rememberManualOrder(testId: string, order: ManualPaymentOut): void {
  try {
    window.sessionStorage.setItem(MANUAL_KEY(testId), JSON.stringify(order));
  } catch {
    // ignore
  }
}

export function recallManualOrder(testId: string): ManualPaymentOut | null {
  try {
    const raw = window.sessionStorage.getItem(MANUAL_KEY(testId));
    return raw ? (JSON.parse(raw) as ManualPaymentOut) : null;
  } catch {
    return null;
  }
}

export function ManualOrderDetails({
  order,
  fallbackPayment,
}: {
  order: ManualPaymentOut | null;
  fallbackPayment: PaymentOut | null;
}) {
  const t = useTranslations("checkout.manual");
  const locale = useLocale();
  const expiresAt = order?.expires_at ?? fallbackPayment?.expires_at ?? null;
  const left = useCountdown(expiresAt);
  const currency = order?.local_currency ?? fallbackPayment?.local_currency ?? "MMK";
  const amountMinor = order?.local_amount_minor ?? fallbackPayment?.local_amount_minor ?? null;
  const code = order?.payment_code ?? fallbackPayment?.payment_code ?? "";
  const expired = left === 0;

  return (
    <div className="space-y-4">
      <Alert variant={expired ? "destructive" : "warning"}>
        <Clock aria-hidden />
        <AlertTitle>{expired ? t("expiredTitle") : t("waitingTitle")}</AlertTitle>
        <AlertDescription>
          {expired ? t("expiredBody") : t("waitingBody")}
          {!expired && left !== null ? (
            <span className="ml-1 tabular">{t("expiresIn", { time: formatCountdown(left) })}</span>
          ) : null}
          {expiresAt ? (
            <span className="block text-xs text-muted-foreground">
              {t("expiresAt", { date: formatDateTime(expiresAt, locale) })}
            </span>
          ) : null}
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>{t("amountTitle")}</CardTitle>
          <CardDescription>{t("amountBody")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-3xl font-semibold tabular">
              {order?.local_display || formatMoney(amountMinor, currency, locale)}
            </p>
            {amountMinor !== null ? (
              <CopyButton value={String(Math.round(amountMinor))} label={t("copyAmount")} />
            ) : null}
            {order ? (
              <span className="text-sm text-muted-foreground">
                {t("usdEquivalent", { usd: order.usd_display, rate: order.fx_rate.toLocaleString(locale) })}
              </span>
            ) : null}
          </div>
          <div className="rounded-md border border-border p-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{t("paymentCode")}</p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <p className="font-mono text-2xl font-semibold tracking-wider">{code}</p>
              {code ? <CopyButton value={code} label={t("copyCode")} /> : null}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{t("codeHint")}</p>
          </div>
        </CardContent>
      </Card>

      {order && order.accounts.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("accountsTitle")}</CardTitle>
            <CardDescription>{order.instructions}</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-border">
              {order.accounts.map((a, i) => (
                <li
                  key={i}
                  className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium">{a.provider}</p>
                    <p className="text-sm text-muted-foreground">{a.account_name}</p>
                    <p className="font-mono text-sm">{a.account_number}</p>
                    {a.note ? <p className="text-xs text-muted-foreground">{a.note}</p> : null}
                  </div>
                  <CopyButton value={a.account_number} label={t("copyAccount")} />
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : !order ? (
        <Alert variant="info">
          <AlertDescription>{t("detailsUnavailable")}</AlertDescription>
        </Alert>
      ) : null}

      {order && Object.keys(order.social_links).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("proofTitle")}</CardTitle>
            <CardDescription>{t("proofBody")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {Object.entries(order.social_links).map(([k, url]) => (
              <Button key={k} asChild variant="outline">
                <a href={url} target="_blank" rel="noopener noreferrer">
                  {titleCase(k)} <ExternalLink aria-hidden />
                </a>
              </Button>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
