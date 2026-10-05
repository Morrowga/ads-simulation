"use client";

import { Building2, Pencil, Plus, Star } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { useProfiles } from "@/lib/queries";
import type { ProfileOut } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { ProfileChoice } from "@/lib/wizard-draft";
import { ProfileEditDialog } from "./profile-edit-dialog";

export function StepPreset({
  value,
  onChange,
  onEditSave,
  saving,
  returnTo,
  preselectId,
}: {
  value: ProfileChoice | null;
  onChange: (c: ProfileChoice) => void;
  onEditSave: (c: ProfileChoice) => Promise<void>;
  saving: boolean;
  returnTo: string;
  preselectId?: string | null;
}) {
  const t = useTranslations("wizard.preset");
  const profiles = useProfiles();
  const [editing, setEditing] = useState(false);
  const active = useMemo(() => (profiles.data ?? []).filter((p) => !p.archived), [profiles.data]);
  const selected: ProfileOut | undefined = active.find((p) => p.id === value?.profile_id);

  // preselect: profile from ?profile= (just created), otherwise the default preset
  useEffect(() => {
    if (value || active.length === 0) return;
    const pick =
      (preselectId && active.find((p) => p.id === preselectId)) ||
      active.find((p) => p.is_default) ||
      active[0];
    if (pick) onChange({ profile_id: pick.id, mode: "preset", changes: {} });
  }, [active, value, onChange, preselectId]);

  if (profiles.isLoading) return <PageSkeleton rows={2} />;
  if (profiles.isError) return <ErrorState error={profiles.error} onRetry={() => profiles.refetch()} />;
  if (active.length === 0) {
    return (
      <EmptyState
        icon={Building2}
        title={t("emptyTitle")}
        description={t("emptyBody")}
        action={
          <Button asChild>
            <Link href={`/profiles/new?return=${encodeURIComponent(returnTo)}`}>
              <Plus aria-hidden /> {t("createProfile")}
            </Link>
          </Button>
        }
      />
    );
  }

  const changedCount = Object.keys(value?.changes ?? {}).length;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {active.map((p) => {
          const on = p.id === value?.profile_id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onChange({ profile_id: p.id, mode: "preset", changes: {} })}
              aria-pressed={on}
              className={cn(
                "rounded-lg border p-4 text-left transition-colors touch-target",
                on ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
              )}
            >
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.name}</span>
                {p.is_default ? (
                  <Badge variant="info">
                    <Star className="mr-1 h-3 w-3" aria-hidden /> {t("default")}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {p.category_name ?? p.category_code} · v{p.current_version}
              </p>
            </button>
          );
        })}
        <Link
          href={`/profiles/new?return=${encodeURIComponent(returnTo)}`}
          className="flex items-center justify-center gap-2 rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground hover:bg-muted/40 touch-target"
        >
          <Plus className="h-4 w-4" aria-hidden /> {t("createProfile")}
        </Link>
      </div>
      {selected ? (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="font-medium">
                {selected.name} <span className="text-muted-foreground">· v{selected.current_version}</span>
                {changedCount > 0 ? (
                  <Badge variant="warning" className="ml-2">
                    {t("editedForThisAd", { count: changedCount })}
                  </Badge>
                ) : null}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">{selected.summary}</p>
            </div>
            <Button type="button" variant="outline" onClick={() => setEditing(true)} className="shrink-0">
              <Pencil aria-hidden /> {t("editForThisAd")}
            </Button>
          </CardContent>
          <ProfileEditDialog
            open={editing}
            onOpenChange={setEditing}
            profile={selected}
            initialChanges={value?.changes ?? {}}
            saving={saving}
            onSave={async (c) => {
              await onEditSave(c);
              setEditing(false);
            }}
          />
        </Card>
      ) : null}
    </div>
  );
}
