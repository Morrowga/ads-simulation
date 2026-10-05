import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/components/layout/auth-gate";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGate admin>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
