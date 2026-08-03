export type AuthAssuranceLevel = "aal1" | "aal2" | null;

export type AuthIdentity = {
  id: string;
  email: string | null;
  assuranceLevel: AuthAssuranceLevel;
};

export type RouteAccessDecision =
  | { kind: "allow" }
  | { kind: "login"; error?: "account_suspended" }
  | { kind: "sandbox"; error: "admin_required" }
  | { kind: "mfa" };

export function isProtectedPath(pathname: string): boolean {
  return (
    pathname === "/sandbox" ||
    pathname.startsWith("/sandbox/") ||
    pathname === "/admin" ||
    pathname.startsWith("/admin/")
  );
}

export function isAdminPath(pathname: string): boolean {
  return pathname === "/admin" || pathname.startsWith("/admin/");
}

export function safeNextPath(
  value: string | null | undefined,
  fallback = "/sandbox",
): string {
  if (
    !value ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    /[\r\n]/.test(value)
  ) {
    return fallback;
  }

  return value;
}

export function decideRouteAccess(
  pathname: string,
  identity: AuthIdentity | null,
  adminUserIds: ReadonlySet<string>,
  suspendedUserIds: ReadonlySet<string>,
): RouteAccessDecision {
  if (!isProtectedPath(pathname)) {
    return { kind: "allow" };
  }

  if (!identity) {
    return { kind: "login" };
  }

  if (suspendedUserIds.has(identity.id)) {
    return { kind: "login", error: "account_suspended" };
  }

  if (!isAdminPath(pathname)) {
    return { kind: "allow" };
  }

  if (!adminUserIds.has(identity.id)) {
    return { kind: "sandbox", error: "admin_required" };
  }

  if (identity.assuranceLevel !== "aal2") {
    return { kind: "mfa" };
  }

  return { kind: "allow" };
}
