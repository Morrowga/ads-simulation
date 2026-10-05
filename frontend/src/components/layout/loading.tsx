import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** Mirrors PageHeader: title + description on the left, action button on the right. */
function HeaderSkeleton() {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-72 max-w-full" />
      </div>
      <Skeleton className="h-10 w-32" />
    </div>
  );
}

/** Mirrors ProfileCard: name, category, date, 2-line summary, version/tests row. */
function CardSkeleton() {
  return (
    <div className="flex flex-col rounded-lg border border-border p-6">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-3 w-32" />
        </div>
        <Skeleton className="h-8 w-8 rounded-md" />
      </div>
      <div className="mt-6 space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  );
}

/** Mirrors a form Card: title + description, then a 2-column grid of label/input pairs. */
function FormCardSkeleton() {
  return (
    <div className="rounded-lg border border-border p-6">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="mt-2 h-4 w-64 max-w-full" />
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-10 w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function PageSkeleton({
  rows = 4,
  variant = "list",
  header = true,
}: {
  rows?: number;
  /** list: stacked rows (default) | cards: profile-card grid | form: form cards */
  variant?: "list" | "cards" | "form";
  /** Set false when the real PageHeader is already on screen above the skeleton. */
  header?: boolean;
}) {
  return (
    <div className="space-y-6" aria-busy="true" aria-live="polite">
      {header ? <HeaderSkeleton /> : null}
      {variant === "cards" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: rows }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : variant === "form" ? (
        <div className="space-y-4">
          {Array.from({ length: rows }).map((_, i) => (
            <FormCardSkeleton key={i} />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {Array.from({ length: rows }).map((_, i) => (
            <Skeleton key={i} className={cn("h-20 w-full")} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Mirrors AppShell exactly (sticky h-14 header, w-60 sidebar with 4 nav items on lg+, main padding).
 * Use it where the shell is not mounted yet, e.g. AuthGate while auth is loading.
 */
export function AppShellSkeleton({ children }: { children?: ReactNode }) {
  return (
    <div className="min-h-dvh bg-background" aria-busy="true" aria-live="polite">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-screen-2xl items-center gap-3 px-4">
          <Skeleton className="h-9 w-9 rounded-md lg:hidden" />
          <div className="flex items-center gap-2">
            <Skeleton className="h-7 w-7 rounded-md" />
            <Skeleton className="h-5 w-16" />
          </div>
          <div className="ml-auto flex items-center gap-1">
            <Skeleton className="hidden h-8 w-24 sm:block" />
            <Skeleton className="h-9 w-9 rounded-md" />
            <Skeleton className="h-8 w-32" />
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-screen-2xl">
        <aside className="hidden w-60 shrink-0 border-r border-border p-4 lg:sticky lg:top-14 lg:block lg:h-[calc(100dvh-3.5rem)] lg:overflow-y-auto">
          <div className="space-y-0.5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-md px-3 py-2.5">
                <Skeleton className="h-4 w-4 shrink-0" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        </aside>
        <main className="min-w-0 flex-1 px-4 py-6 sm:px-6 lg:px-8">
          {children ?? <PageSkeleton />}
        </main>
      </div>
    </div>
  );
}