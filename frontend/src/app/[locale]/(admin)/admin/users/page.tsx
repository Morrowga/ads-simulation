"use client";

import { Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { ConfirmDialog } from "@/components/layout/confirm-dialog";
import { CursorPager, useCursorPager } from "@/components/layout/cursor-pager";
import { EmptyState } from "@/components/layout/empty-state";
import { ErrorState } from "@/components/layout/error-state";
import { PageSkeleton } from "@/components/layout/loading";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/components/ui/toaster";
import { useApiError } from "@/hooks/use-api-error";
import { Link } from "@/i18n/navigation";
import { formatDateTime } from "@/lib/format";
import { useAdminMutations, useAdminUsers } from "@/lib/queries";
import type { AdminUserOut } from "@/lib/types";

type Pending = {
  user: AdminUserOut;
  action: "block" | "unblock" | "reset_trial" | "make_admin" | "make_user";
} | null;

export default function AdminUsersPage() {
  const t = useTranslations("admin.users");
  const locale = useLocale();
  const { toast } = useToast();
  const msg = useApiError();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const pager = useCursorPager();
  const users = useAdminUsers(q || null, pager.cursor);
  const m = useAdminMutations();
  const [pending, setPending] = useState<Pending>(null);

  const apply = async () => {
    if (!pending) return;
    const body =
      pending.action === "block"
        ? { is_blocked: true }
        : pending.action === "unblock"
          ? { is_blocked: false }
          : pending.action === "reset_trial"
            ? { reset_trial: true }
            : { role: pending.action === "make_admin" ? "admin" : "user" };
    try {
      await m.patchUser.mutateAsync({ id: pending.user.id, body });
      toast({ title: t("done"), variant: "success" });
      setPending(null);
    } catch (e) {
      toast({ title: msg(e), variant: "destructive" });
    }
  };

  return (
    <>
      <PageHeader title={t("title")} description={t("description")} />
      <form
        className="mb-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(query.trim());
          pager.reset();
        }}
      >
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("searchPlaceholder")}
          aria-label={t("search")}
          className="max-w-md"
        />
        <Button type="submit" variant="outline" aria-label={t("search")}>
          <Search aria-hidden />
        </Button>
      </form>
      {users.isLoading ? <PageSkeleton rows={3} /> : null}
      {users.isError ? <ErrorState error={users.error} onRetry={() => users.refetch()} /> : null}
      {users.data && users.data.items.length === 0 ? <EmptyState title={t("empty")} /> : null}
      {users.data && users.data.items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("cols.user")}</TableHead>
              <TableHead>{t("cols.role")}</TableHead>
              <TableHead>{t("cols.flags")}</TableHead>
              <TableHead className="text-right">{t("cols.tests")}</TableHead>
              <TableHead>{t("cols.created")}</TableHead>
              <TableHead className="text-right">{t("cols.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.data.items.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <p className="font-medium">{u.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {u.email} · {u.country ?? "—"}
                  </p>
                </TableCell>
                <TableCell>
                  <Badge variant={u.role === "admin" ? "info" : "neutral"}>{u.role}</Badge>
                </TableCell>
                <TableCell className="space-x-1">
                  {u.is_blocked ? <Badge variant="danger">{t("blocked")}</Badge> : null}
                  {!u.email_verified ? <Badge variant="warning">{t("unverified")}</Badge> : null}
                  {u.trial_used ? <Badge variant="neutral">{t("trialUsed")}</Badge> : null}
                  {u.deleted_at ? <Badge variant="neutral">{t("deleted")}</Badge> : null}
                </TableCell>
                <TableCell className="text-right tabular">
                  <Link
                    href={`/admin/tests?email=${encodeURIComponent(u.email)}`}
                    className="text-primary hover:underline"
                  >
                    {u.tests_count}
                  </Link>
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs">
                  {formatDateTime(u.created_at, locale)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex flex-wrap justify-end gap-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPending({ user: u, action: u.is_blocked ? "unblock" : "block" })}
                    >
                      {u.is_blocked ? t("unblock") : t("block")}
                    </Button>
                    {u.trial_used ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setPending({ user: u, action: "reset_trial" })}
                      >
                        {t("resetTrial")}
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setPending({ user: u, action: u.role === "admin" ? "make_user" : "make_admin" })
                      }
                    >
                      {u.role === "admin" ? t("makeUser") : t("makeAdmin")}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
      <CursorPager pager={pager} nextCursor={users.data?.next_cursor} />
      <ConfirmDialog
        open={!!pending}
        onOpenChange={(o) => !o && setPending(null)}
        title={pending ? t(`confirm.${pending.action}.title`, { email: pending.user.email }) : ""}
        description={pending ? t(`confirm.${pending.action}.body`) : ""}
        destructive={pending?.action === "block"}
        loading={m.patchUser.isPending}
        onConfirm={apply}
      />
    </>
  );
}
