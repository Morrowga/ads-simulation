import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { PageSkeleton } from "./loading";

/** Mirrors AppShell: sticky header, 240px sidebar with 4 nav items (lg+), main content area. */
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
          <div className="ml-auto flex items-center gap-2">
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