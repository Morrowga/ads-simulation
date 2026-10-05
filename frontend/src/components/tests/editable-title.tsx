"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Pencil, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { useTestMutations } from "@/lib/queries";

type EditableTitleProps = {
  value: string;
  /** Persist the new (already trimmed) title. Throw to show an inline error. */
  onSave: (title: string) => Promise<void> | void;
  disabled?: boolean;
  maxLength?: number;
  /** Shown (muted) when value is empty, e.g. "New test" */
  placeholder?: string;
  className?: string;
  textClassName?: string;
};

export function EditableTitle({
  value,
  onSave,
  disabled,
  maxLength = 160,
  placeholder,
  className,
  textClassName,
}: EditableTitleProps) {
  const t = useTranslations("testTitle");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const skipBlur = useRef(false);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  function start() {
    if (disabled || saving) return;
    skipBlur.current = false;
    setDraft(value);
    setError(null);
    setEditing(true);
  }

  function cancel() {
    skipBlur.current = true;
    setEditing(false);
    setError(null);
    setDraft(value);
  }

  async function commit() {
    if (saving) return;
    const next = draft.trim();
    if (!next) {
      setError(t("empty"));
      inputRef.current?.focus();
      return;
    }
    if (next.length > maxLength) {
      setError(t("tooLong", { max: maxLength }));
      return;
    }
    if (next === value.trim()) {
      skipBlur.current = true;
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSave(next);
      skipBlur.current = true;
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t("failed"));
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
        <span
          onDoubleClick={start}
          title={disabled ? undefined : t("hint")}
          className={cn(
            "min-w-0 truncate",
            !disabled && "cursor-text",
            !value && "text-muted-foreground",
            textClassName,
          )}
        >
          {value || placeholder}
        </span>
        {!disabled && (
          <button
            type="button"
            onClick={start}
            aria-label={t("edit")}
            className="touch-target inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[#0071b5] transition-colors hover:bg-[#0071b5]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0071b5]"
          >
            <Pencil className="h-4 w-4" />
          </button>
        )}
      </span>
    );
  }

  return (
    <span className={cn("inline-flex min-w-0 max-w-full flex-col gap-1", className)}>
      <span className="inline-flex items-center gap-1">
        <Input
          ref={inputRef}
          value={draft}
          maxLength={maxLength + 40}
          disabled={saving}
          aria-label={t("edit")}
          aria-invalid={!!error}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void commit();
            } else if (e.key === "Escape") {
              e.preventDefault();
              cancel();
            }
          }}
          onBlur={() => {
            if (skipBlur.current) return;
            if (!draft.trim()) cancel();
            else void commit();
          }}
          className={cn(
            "h-auto w-[min(28rem,70vw)] rounded-none border-0 border-b-2 border-primary/40 bg-transparent px-0 py-0.5 shadow-none",
            "focus-visible:border-primary focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0",
            "disabled:opacity-60 aria-[invalid=true]:border-destructive",
            "text-[length:inherit] font-[inherit] leading-[inherit] tracking-[inherit]",
            textClassName,
          )}
        />
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => void commit()}
          disabled={saving}
          aria-label={t("save")}
          className="touch-target inline-flex h-8 w-8 items-center justify-center rounded-md text-[#0071b5] hover:bg-muted"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={cancel}
          disabled={saving}
          aria-label={t("cancel")}
          className="touch-target inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
        >
          <X className="h-4 w-4" />
        </button>
      </span>
      {error && (
        <span role="alert" className="text-xs font-normal text-destructive">
          {error}
        </span>
      )}
    </span>
  );
}

/** Drop-in for any page that already has a saved test (detail, confirm, report, live, checkout). */
export function TestTitle({
  testId,
  title,
  disabled,
  className,
  textClassName,
}: {
  testId: string;
  title: string;
  disabled?: boolean;
  className?: string;
  textClassName?: string;
}) {
  const m = useTestMutations(testId);
  return (
    <EditableTitle
      value={title}
      disabled={disabled}
      className={className}
      textClassName={textClassName}
      onSave={async (next) => {
        await m.update.mutateAsync({ testId, body: { title: next } });
      }}
    />
  );
}