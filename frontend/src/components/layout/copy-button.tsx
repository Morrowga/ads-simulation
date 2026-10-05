"use client";

import { Check, Copy } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export function CopyButton({
  value,
  label,
  size = "sm",
}: {
  value: string;
  label?: string;
  size?: "sm" | "icon";
}) {
  const t = useTranslations("common");
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    } catch {
      // clipboard blocked: the value stays visible for manual copy
    }
  };
  return (
    <Button
      type="button"
      variant="outline"
      size={size}
      onClick={copy}
      aria-label={label ?? t("copy")}
      className="touch-target"
    >
      {done ? <Check aria-hidden /> : <Copy aria-hidden />}
      {size === "sm" ? (done ? t("copied") : (label ?? t("copy"))) : null}
    </Button>
  );
}
