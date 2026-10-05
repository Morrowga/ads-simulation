"use client";

/** Minimal accessible toast system (no extra dependency). */
import { X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ToastInput {
  title: string;
  description?: string;
  variant?: "default" | "success" | "destructive";
  durationMs?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

interface ToastContextValue {
  toast: (t: ToastInput) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);
  const toast = useCallback(
    (t: ToastInput) => {
      const id = Date.now() + Math.random();
      setItems((list) => [...list.slice(-4), { ...t, id }]);
      window.setTimeout(() => dismiss(id), t.durationMs ?? (t.variant === "destructive" ? 8000 : 4500));
    },
    [dismiss],
  );
  const value = useMemo(() => ({ toast }), [toast]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2"
        aria-live="polite"
        aria-atomic="false"
      >
        {items.map((t) => (
          <div
            key={t.id}
            role={t.variant === "destructive" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto flex items-center gap-3 rounded-lg border px-4 py-3 shadow-lg bg-background text-foreground",
              t.variant === "success" && "border-[#0071b5]",
              t.variant === "destructive" && "border-danger/40",
              (!t.variant || t.variant === "default") && "border-border",
            )}
          >
            <div className="flex-1 space-y-0.5">
              <p className="text-sm font-medium">{t.title}</p>
              {t.description ? <p className="text-sm text-muted-foreground">{t.description}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm opacity-70 hover:opacity-100"
              aria-label="Dismiss"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
