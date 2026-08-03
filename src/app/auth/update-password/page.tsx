import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { PasswordSetupForm } from "@/components/auth/PasswordSetupForm";
import { requireUser } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Choose a new password",
};

export default async function UpdatePasswordPage() {
  await requireUser("/auth/update-password");

  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Choose a new password"
      description="Your recovery link has been verified. Set a new password to continue."
    >
      <PasswordSetupForm submitLabel="Update password" />
    </AuthShell>
  );
}
