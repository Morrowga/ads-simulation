"use client";

import { useTranslations } from "next-intl";
import { Controller, type UseFormReturn } from "react-hook-form";
import { FormField } from "@/components/layout/form-field";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { AdStepValues } from "@/lib/schemas";
import { CTAS, type AssetOut } from "@/lib/types";
import { type QueuedFile, UploadDropzone } from "./upload-dropzone";

export function StepAd({
  form,
  testId,
  assets,
  queued,
  onQueuedChange,
  onUploaded,
  onDeleteAsset,
  mediaError,
}: {
  form: UseFormReturn<AdStepValues>;
  testId: string | null;
  assets: AssetOut[];
  queued: QueuedFile[];
  onQueuedChange: (u: (q: QueuedFile[]) => QueuedFile[]) => void;
  onUploaded: (a: AssetOut) => void;
  onDeleteAsset: (id: string) => Promise<void>;
  mediaError: string | null;
}) {
  const t = useTranslations("wizard.ad");
  const e = form.formState.errors;
  const caption = form.watch("caption");
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("mediaTitle")}</CardTitle>
          <CardDescription>{t("mediaBody")}</CardDescription>
        </CardHeader>
        <CardContent>
          <UploadDropzone
            testId={testId}
            assets={assets}
            queued={queued}
            onQueuedChange={onQueuedChange}
            onUploaded={onUploaded}
            onDeleteAsset={onDeleteAsset}
          />
          {mediaError ? (
            <p role="alert" className="mt-2 text-sm text-danger">
              {mediaError}
            </p>
          ) : null}
          {!testId && queued.length > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">{t("queuedNote")}</p>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("copyTitle")}</CardTitle>
          <CardDescription>{t("copyBody")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <FormField
            id="title"
            label={t("fields.title")}
            error={e.title}
            required
            help={t("fields.titleHelp")}
            className="sm:col-span-2"
          >
            <Input id="title" maxLength={160} aria-invalid={!!e.title} {...form.register("title")} />
          </FormField>
          <FormField
            id="caption"
            label={t("fields.caption")}
            error={e.caption}
            help={t("fields.captionHelp")}
            hint={`${caption.length} / 2200`}
            className="sm:col-span-2"
          >
            <Textarea
              id="caption"
              rows={5}
              maxLength={2200}
              aria-invalid={!!e.caption}
              {...form.register("caption")}
            />
          </FormField>
          <FormField
            id="headline"
            label={t("fields.headline")}
            error={e.headline}
            help={t("fields.headlineHelp")}
          >
            <Input id="headline" maxLength={200} aria-invalid={!!e.headline} {...form.register("headline")} />
          </FormField>
          <FormField id="cta" label={t("fields.cta")} error={e.cta} required>
            <Controller
              control={form.control}
              name="cta"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="cta">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CTAS.map((c) => (
                      <SelectItem key={c} value={c}>
                        {t(`cta.${c}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
          <FormField
            id="link_url"
            label={t("fields.link")}
            error={e.link_url}
            help={t("fields.linkHelp")}
            className="sm:col-span-2"
          >
            <Input
              id="link_url"
              type="url"
              inputMode="url"
              placeholder="https://"
              aria-invalid={!!e.link_url}
              {...form.register("link_url")}
            />
          </FormField>
        </CardContent>
      </Card>
    </div>
  );
}
