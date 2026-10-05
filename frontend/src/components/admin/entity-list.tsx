"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface EntityRow {
  code: string;
  name: string;
  meta?: string;
  badges?: { label: string; variant: "success" | "warning" | "neutral" | "info" | "danger" }[];
}

export function EntityList({
  rows,
  selected,
  onSelect,
  label,
}: {
  rows: EntityRow[];
  selected: string | null;
  onSelect: (code: string) => void;
  label: string;
}) {
  return (
    <ul className="divide-y divide-border rounded-lg border border-border" aria-label={label}>
      {rows.map((r) => (
        <li key={r.code}>
          <button
            type="button"
            onClick={() => onSelect(r.code)}
            aria-pressed={selected === r.code}
            className={cn(
              "flex w-full flex-col gap-1 p-3 text-left text-sm hover:bg-muted/40 touch-target",
              selected === r.code && "bg-primary/5",
            )}
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{r.name}</span>
              <span className="font-mono text-xs text-muted-foreground">{r.code}</span>
              {r.badges?.map((b) => (
                <Badge key={b.label} variant={b.variant}>
                  {b.label}
                </Badge>
              ))}
            </span>
            {r.meta ? <span className="text-xs text-muted-foreground">{r.meta}</span> : null}
          </button>
        </li>
      ))}
    </ul>
  );
}
