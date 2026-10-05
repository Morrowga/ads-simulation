"use client";

import { useParams } from "next/navigation";
import { ProfileEditor } from "@/components/profile/profile-editor";

export default function EditProfilePage() {
  const { id } = useParams<{ id: string }>();
  return <ProfileEditor profileId={id} />;
}
