import type { Metadata } from "next";

import { AuthShell } from "@/components/auth/AuthShell";
import { LoginForm } from "@/components/auth/LoginForm";
import { safeNextPath } from "@/lib/auth/routing";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to an invited LunarForge sandbox account.",
};

const ERRORS: Record<string, string> = {
  account_suspended: "This account has been suspended. Contact the owner.",
  auth_callback_failed: "That sign-in link is invalid or has expired.",
  invite_expired: "That invitation is invalid or has expired. Ask for a new invitation.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>;
}) {
  const params = await searchParams;
  const error = params.error ? ERRORS[params.error] : undefined;

  return (
    <AuthShell
      eyebrow="Private sandbox"
      title="Welcome back"
      description="Sign in with the email and password attached to your individual invitation."
    >
      <LoginForm
        nextPath={safeNextPath(params.next)}
        initialError={error}
      />
    </AuthShell>
  );
}
