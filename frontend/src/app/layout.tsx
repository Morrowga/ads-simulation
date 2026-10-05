import type { ReactNode } from "react";

// Pass-through root layout: <html>/<body> are rendered by app/[locale]/layout.tsx
// (and by app/not-found.tsx for URLs outside a locale).
export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}