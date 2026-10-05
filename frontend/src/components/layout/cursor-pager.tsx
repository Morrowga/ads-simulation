"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";

/** Cursor pagination state: a stack of previous cursors so "Previous" works. */
export function useCursorPager() {
  const [stack, setStack] = useState<(string | null)[]>([null]);
  const cursor = stack[stack.length - 1] ?? null;
  const next = useCallback((c: string) => setStack((s) => [...s, c]), []);
  const prev = useCallback(() => setStack((s) => (s.length > 1 ? s.slice(0, -1) : s)), []);
  const reset = useCallback(() => setStack([null]), []);
  return { cursor, next, prev, reset, canPrev: stack.length > 1 };
}

export function CursorPager({
  pager,
  nextCursor,
}: {
  pager: ReturnType<typeof useCursorPager>;
  nextCursor: string | null | undefined;
}) {
  const t = useTranslations("common");
  if (!pager.canPrev && !nextCursor) return null;
  return (
    <div className="mt-4 flex items-center justify-end gap-2">
      <Button variant="outline" size="sm" onClick={pager.prev} disabled={!pager.canPrev}>
        <ChevronLeft aria-hidden /> {t("previous")}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => nextCursor && pager.next(nextCursor)}
        disabled={!nextCursor}
      >
        {t("next")} <ChevronRight aria-hidden />
      </Button>
    </div>
  );
}
