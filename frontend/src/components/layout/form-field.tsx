"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import type { FieldError } from "react-hook-form";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Label + control + linked error/help text (WCAG: errors linked to inputs via aria-describedby). */
export function FormField({
  id,
  label,
  error,
  help,
  required,
  children,
  className,
  hint,
}: {
  id: string;
  label: ReactNode;
  error?: FieldError | string;
  help?: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const t = useTranslations("validation");
  const message = typeof error === "string" ? error : error?.message;
  const text = message ? (t.has(message) ? t(message) : message) : null;
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <Label htmlFor={id}>
          {label}
          {required ? (
            <span className="text-danger" aria-hidden>
              {" "}
              *
            </span>
          ) : null}
        </Label>
        {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
      </div>
      {children}
      {text ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-danger">
          {text}
        </p>
      ) : help ? (
        <p id={`${id}-help`} className="text-xs text-muted-foreground">
          {help}
        </p>
      ) : null}
    </div>
  );
}

export function describedBy(id: string, error?: FieldError | string, help?: ReactNode): string | undefined {
  if (error) return `${id}-error`;
  if (help) return `${id}-help`;
  return undefined;
}
