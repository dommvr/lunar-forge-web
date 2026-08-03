import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { PasswordSetupForm } from "@/components/auth/PasswordSetupForm";
import { requireUser } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Accept invitation",
};

export default async function SetupPasswordPage() {
  await requireUser("/auth/setup-password");

  return (
    <AuthShell
      eyebrow="Invitation accepted"
      title="Create your password"
      description="Finish your individual LunarForge account. This password is never shared with other visitors."
    >
      <PasswordSetupForm />
    </AuthShell>
  );
}
