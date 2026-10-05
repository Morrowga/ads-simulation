"use client";

import { Archive, Copy, MoreHorizontal, Pencil, Star } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link, useRouter } from "@/i18n/navigation";
import { formatDate } from "@/lib/format";
import { useProfileMutations, useProfileVersions } from "@/lib/queries";
import type { ProfileOut } from "@/lib/types";

/** Preset card with version, last used date and number of tests (computed from /profiles/{id}/versions). */
export function ProfileCard({ profile }: { profile: ProfileOut }) {
  const t = useTranslations("profiles");
  const locale = useLocale();
  const router = useRouter();
  const { toast } = useToast();
  const msg = useApiError();
  const versions = useProfileVersions(profile.id, { staleTime: 60_000 });
  const { duplicate, archive } = useProfileMutations();
  const [confirmArchive, setConfirmArchive] = useState(false);

  const tests = (versions.data ?? []).flatMap(
    (v) => (v.tests ?? []) as { id: string; title: string; status: string }[],
  );
  const lastUsed = versions.data && versions.data.length > 0 ? versions.data[0].created_at : null;

  const onDuplicate = async () => {
    try {
      const p = await duplicate.mutateAsync({ id: profile.id, name: t("copyName", { name: profile.name }) });
      toast({ title: t("duplicated"), variant: "success" });
      router.push(`/profiles/${p.id}`);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };
  const onArchive = async () => {
    try {
      await archive.mutateAsync(profile.id);
      setConfirmArchive(false);
      toast({ title: t("archived"), variant: "success" });
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  const testCountLabel = versions.isLoading ? "…" : String(tests.length);

  return (
    <Card className="flex flex-col overflow-hidden">
      <CardHeader className="flex-row items-start justify-between gap-2 space-y-0">
        <div className="min-w-0">
          <CardTitle className="flex items-center gap-2 truncate">
            <Link href={`/profiles/${profile.id}`} className="truncate hover:underline">
              {profile.name}
            </Link>
            {profile.is_default ? (
              <Badge variant="info" className="shrink-0">
                <Star className="mr-1 h-3 w-3" aria-hidden /> {t("default")}
              </Badge>
            ) : null}
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {profile.category_name ?? profile.category_code}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {t("lastUsed")}: {formatDate(lastUsed ?? profile.updated_at, locale)}
          </p>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t("actions")} className="touch-target">
              <MoreHorizontal aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => router.push(`/profiles/${profile.id}`)}>
              <Pencil aria-hidden /> {t("edit")}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={onDuplicate}>
              <Copy aria-hidden /> {t("duplicate")}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setConfirmArchive(true)}>
              <Archive aria-hidden /> {t("archive")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </CardHeader>
      <CardContent className="mt-auto space-y-3">
        <p className="line-clamp-2 text-sm text-muted-foreground">{profile.summary}</p>
        <div className="flex items-center justify-between text-xs">
          <p>
            <span className="text-muted-foreground">{t("version")}</span>{" "}
            <span className="font-medium tabular">v{profile.current_version}</span>
          </p>
          <p>
            <span className="text-muted-foreground">{t("tests")}</span>{" "}
            <span className="font-medium tabular">{testCountLabel}</span>
          </p>
        </div>
      </CardContent>
      <ConfirmDialog
        open={confirmArchive}
        onOpenChange={setConfirmArchive}
        title={t("archiveTitle", { name: profile.name })}
        description={t("archiveBody")}
        confirmLabel={t("archive")}
        destructive
        loading={archive.isPending}
        onConfirm={onArchive}
      />
    </Card>
  );
}