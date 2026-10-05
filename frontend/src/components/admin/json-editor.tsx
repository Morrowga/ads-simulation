"use client";

/** JSON editor with live validation, used for the data blobs of versioned settings. */
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export function JsonEditor({
  id,
  value,
  onChange,
  rows = 18,
  label,
  disabled,
}: {
  id: string;
  value: unknown;
  onChange: (v: Record<string, unknown> | null) => void;
  rows?: number;
  label: string;
  disabled?: boolean;
}) {
  const t = useTranslations("admin.common");
  const [text, setText] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(JSON.stringify(value ?? {}, null, 2));
    setError(null);
  }, [value]);

  const change = (next: string) => {
    setText(next);
    try {
      const parsed = JSON.parse(next) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError(t("jsonObject"));
        onChange(null);
        return;
      }
      setError(null);
      onChange(parsed as Record<string, unknown>);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("jsonInvalid"));
      onChange(null);
    }
  };

  return (
    <div className="space-y-1.5">
      <Textarea
        id={id}
        aria-label={label}
        value={text}
        onChange={(e) => change(e.target.value)}
        rows={rows}
        spellCheck={false}
        disabled={disabled}
        className={cn("font-mono text-xs leading-relaxed", error && "border-danger")}
        aria-invalid={!!error}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">{t("jsonHint")}</p>
      )}
    </div>
  );
}
