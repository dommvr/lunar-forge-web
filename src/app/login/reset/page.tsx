import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { ResetRequestForm } from "@/components/auth/ResetRequestForm";

export const metadata: Metadata = {
  title: "Reset password",
};

export default function ResetPasswordPage() {
  return (
    <AuthShell
      eyebrow="Account recovery"
      title="Reset your password"
      description="Enter your invited account email. For privacy, the result is the same whether or not an account is found."
    >
      <ResetRequestForm />
    </AuthShell>
  );
}
