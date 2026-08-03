import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth/AuthShell";
import { MfaForm } from "@/components/auth/MfaForm";
import { safeNextPath } from "@/lib/auth/routing";
import { requireAdminBeforeMfa } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Admin verification",
};

export default async function MfaPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const [identity, params] = await Promise.all([
    requireAdminBeforeMfa(),
    searchParams,
  ]);
  const nextPath = safeNextPath(params.next, "/admin");

  if (identity.assuranceLevel === "aal2") {
    redirect(nextPath);
  }

  return (
    <AuthShell
      eyebrow="Administrator"
      title="Verify it’s you"
      description="Administrator sessions require a time-based one-time password after password sign-in."
    >
      <MfaForm nextPath={nextPath} />
    </AuthShell>
  );
}
