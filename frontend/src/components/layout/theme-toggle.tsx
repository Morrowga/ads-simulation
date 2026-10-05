"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

export function ThemeToggle() {
  const t = useTranslations("common");
  const [theme, setTheme] = useTheme();
  // Read the class the inline THEME_INIT_SCRIPT already applied, instead of recomputing
  // matchMedia during render — that recompute is what caused the hydration mismatch, since
  // `window` exists on the client's very first render pass but not on the server's.
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, [theme]);
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? t("lightMode") : t("darkMode")}
      className="touch-target"
    >
      {isDark ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}