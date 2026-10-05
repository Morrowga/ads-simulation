"use client";

/** Version list for a settings kind with publish (change note) and one-click rollback. */
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { FormField } from "@/components/layout/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { formatDateTime } from "@/lib/format";
import { useAdminMutations } from "@/lib/queries";
import type { SettingsVersionOut } from "@/lib/types";

export type VersionLike = Pick<
  SettingsVersionOut,
  "id" | "version" | "status" | "change_note" | "created_at" | "published_at"
>;

export function VersionStatusBadge({ status }: { status: string }) {
  const t = useTranslations("admin.common");
  const v = status === "published" ? "success" : status === "draft" ? "warning" : "neutral";
  return <Badge variant={v}>{t(`versionStatus.${status}` as never)}</Badge>;
}

export function VersionHistory({
  kind,
  versions,
  onChanged,
  onSelect,
  selectedId,
}: {
  kind: string;
  versions: VersionLike[];
  onChanged?: () => void;
  onSelect?: (v: VersionLike) => void;
  selectedId?: string | null;
}) {
  const t = useTranslations("admin.common");
  const locale = useLocale();
  const { toast } = useToast();
  const msg = useApiError();
  const m = useAdminMutations();
  const [publishing, setPublishing] = useState<VersionLike | null>(null);
  const [rollingBack, setRollingBack] = useState<VersionLike | null>(null);
  const [note, setNote] = useState("");
  const published = versions.find((v) => v.status === "published");

  const publish = async () => {
    if (!publishing) return;
    try {
      await m.publish.mutateAsync({ kind, id: publishing.id, note: note || t("publishedNote") });
      toast({ title: t("published"), variant: "success" });
      setPublishing(null);
      setNote("");
      onChanged?.();
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const rollback = async () => {
    if (!rollingBack || !published) return;
    try {
      await m.rollback.mutateAsync({
        kind,
        id: published.id,
        toVersion: rollingBack.version,
        note: note || t("rollbackNote", { version: rollingBack.version }),
      });
      toast({ title: t("rolledBack"), variant: "success" });
      setRollingBack(null);
      setNote("");
      onChanged?.();
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  return (
    <div className="space-y-2">
      <ol className="divide-y divide-border rounded-lg border border-border">
        {versions.map((v) => (
          <li
            key={v.id}
            className={`flex flex-col gap-2 p-3 text-sm sm:flex-row sm:items-center sm:justify-between ${selectedId === v.id ? "bg-primary/5" : ""}`}
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium tabular">v{v.version}</span>
                <VersionStatusBadge status={v.status} />
                <span className="text-xs text-muted-foreground">
                  {formatDateTime(v.published_at ?? v.created_at, locale)}
                </span>
              </div>
              <p className="truncate text-xs text-muted-foreground">{v.change_note || "—"}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {onSelect ? (
                <Button
                  size="sm"
                  variant={selectedId === v.id ? "default" : "outline"}
                  onClick={() => onSelect(v)}
                >
                  {t("view")}
                </Button>
              ) : null}
              {v.status === "draft" ? (
                <Button size="sm" onClick={() => setPublishing(v)}>
                  {t("publish")}
                </Button>
              ) : null}
              {v.status === "archived" && published ? (
                <Button size="sm" variant="outline" onClick={() => setRollingBack(v)}>
                  {t("rollback")}
                </Button>
              ) : null}
            </div>
          </li>
        ))}
        {versions.length === 0 ? (
          <li className="p-3 text-sm text-muted-foreground">{t("noVersions")}</li>
        ) : null}
      </ol>

      <Dialog open={!!publishing} onOpenChange={(o) => !o && setPublishing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("publishTitle", { version: publishing?.version ?? "" })}</DialogTitle>
            <DialogDescription>{t("publishBody")}</DialogDescription>
          </DialogHeader>
          <FormField id="publish-note" label={t("changeNote")} required>
            <Input id="publish-note" value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />
          </FormField>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPublishing(null)}>
              {t("cancel")}
            </Button>
            <Button onClick={publish} loading={m.publish.isPending} disabled={!note.trim()}>
              {t("publish")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!rollingBack} onOpenChange={(o) => !o && setRollingBack(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("rollbackTitle", { version: rollingBack?.version ?? "" })}</DialogTitle>
            <DialogDescription>{t("rollbackBody")}</DialogDescription>
          </DialogHeader>
          <FormField id="rollback-note" label={t("changeNote")}>
            <Input
              id="rollback-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={300}
            />
          </FormField>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRollingBack(null)}>
              {t("cancel")}
            </Button>
            <Button onClick={rollback} loading={m.rollback.isPending}>
              {t("rollback")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
