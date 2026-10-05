"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Input } from "@/components/ui/input";

/** Simple tag input: Enter or comma adds a tag; Backspace on empty removes the last one. */
export function TagPicker({
  id,
  value,
  onChange,
  placeholder,
  max = 20,
}: {
  id: string;
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  max?: number;
}) {
  const t = useTranslations("common");
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim().replace(/,$/, "");
    if (v && !value.includes(v) && value.length < max) onChange([...value, v]);
    setDraft("");
  };
  return (
    <div className="rounded-md border border-input p-1.5">
      <div className="flex flex-wrap gap-1.5">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((x) => x !== tag))}
              aria-label={t("removeTag", { tag })}
              className="rounded-full hover:bg-background"
            >
              <X className="h-3 w-3" aria-hidden />
            </button>
          </span>
        ))}
        <Input
          id={id}
          value={draft}
          placeholder={placeholder}
          className="h-8 min-w-[8rem] flex-1 border-0 shadow-none focus-visible:outline-none"
          onChange={(e) => {
            if (e.target.value.endsWith(",")) {
              setDraft(e.target.value);
              add();
            } else setDraft(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            } else if (e.key === "Backspace" && !draft && value.length) onChange(value.slice(0, -1));
          }}
          onBlur={add}
        />
      </div>
    </div>
  );
}
