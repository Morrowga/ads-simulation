"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ProfileEditor } from "@/components/profile/profile-editor";

function NewProfile() {
  const params = useSearchParams();
  const returnTo = params.get("return");
  return <ProfileEditor returnTo={returnTo && returnTo.startsWith("/") ? returnTo : undefined} />;
}

export default function NewProfilePage() {
  return (
    <Suspense>
      <NewProfile />
    </Suspense>
  );
}
