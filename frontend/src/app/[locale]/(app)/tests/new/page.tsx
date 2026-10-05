"use client";

import { Suspense } from "react";
import { PageSkeleton } from "@/components/layout/loading";
import { Wizard } from "@/components/wizard/wizard";

export default function NewTestPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Wizard />
    </Suspense>
  );
}
