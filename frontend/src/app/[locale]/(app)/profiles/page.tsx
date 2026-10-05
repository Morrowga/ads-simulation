"use client";

import { Building2, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { ProfileCard } from "@/components/profile/profile-card";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { useProfiles } from "@/lib/queries";

export default function ProfilesPage() {
  const t = useTranslations("profiles");
  const profiles = useProfiles();
  return (
    <>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button asChild>
            <Link href="/profiles/new">
              <Plus aria-hidden /> {t("new")}
            </Link>
          </Button>
        }
      />
      {profiles.isLoading ? <PageSkeleton /> : null}
      {profiles.isError ? <ErrorState error={profiles.error} onRetry={() => profiles.refetch()} /> : null}
      {profiles.data && profiles.data.length === 0 ? (
        <EmptyState
          icon={Building2}
          title={t("emptyTitle")}
          description={t("emptyBody")}
          action={
            <Button asChild>
              <Link href="/profiles/new">{t("new")}</Link>
            </Button>
          }
        />
      ) : null}
      {profiles.data && profiles.data.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {profiles.data.map((p) => (
            <ProfileCard key={p.id} profile={p} />
          ))}
        </div>
      ) : null}
    </>
  );
}
