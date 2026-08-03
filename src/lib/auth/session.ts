import "server-only";

import type { JwtPayload } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getAdminUserIds, getSuspendedUserIds } from "./config";
import type { AuthAssuranceLevel, AuthIdentity } from "./routing";
import { safeNextPath } from "./routing";
import { createServerSupabaseClient } from "./server";
import { AUTH_E2E_COOKIE, getE2EIdentity, isAuthE2EMode } from "./test-mode";

function getAssuranceLevel(claims: JwtPayload): AuthAssuranceLevel {
  return claims.aal === "aal2" ? "aal2" : claims.aal === "aal1" ? "aal1" : null;
}

function identityFromClaims(claims: JwtPayload): AuthIdentity | null {
  if (typeof claims.sub !== "string" || !claims.sub) {
    return null;
  }

  return {
    id: claims.sub,
    email: typeof claims.email === "string" ? claims.email : null,
    assuranceLevel: getAssuranceLevel(claims),
  };
}

export async function getOptionalIdentity(): Promise<AuthIdentity | null> {
  if (isAuthE2EMode()) {
    const cookieStore = await cookies();
    return getE2EIdentity(cookieStore.get(AUTH_E2E_COOKIE)?.value);
  }

  const supabase = await createServerSupabaseClient();
  const { data, error } = await supabase.auth.getClaims();

  if (error || !data?.claims) {
    return null;
  }

  return identityFromClaims(data.claims);
}

function loginLocation(nextPath: string, error?: string): string {
  const params = new URLSearchParams({ next: safeNextPath(nextPath) });
  if (error) {
    params.set("error", error);
  }
  return `/login?${params.toString()}`;
}

export async function requireUser(nextPath = "/sandbox"): Promise<AuthIdentity> {
  const identity = await getOptionalIdentity();

  if (!identity) {
    redirect(loginLocation(nextPath));
  }

  if (getSuspendedUserIds().has(identity.id)) {
    redirect(loginLocation(nextPath, "account_suspended"));
  }

  return identity;
}

export async function requireAdmin(nextPath = "/admin"): Promise<AuthIdentity> {
  const identity = await requireUser(nextPath);

  if (!getAdminUserIds().has(identity.id)) {
    redirect("/sandbox?error=admin_required");
  }

  if (identity.assuranceLevel !== "aal2") {
    redirect(`/auth/mfa?next=${encodeURIComponent(safeNextPath(nextPath, "/admin"))}`);
  }

  return identity;
}

export async function requireAdminBeforeMfa(): Promise<AuthIdentity> {
  const identity = await requireUser("/admin");

  if (!getAdminUserIds().has(identity.id)) {
    redirect("/sandbox?error=admin_required");
  }

  return identity;
}
