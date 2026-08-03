import type { AuthIdentity } from "./routing";

export const AUTH_E2E_COOKIE = "lf-auth-e2e";

type RuntimeEnvironment = Record<string, string | undefined>;

export function isAuthE2EMode(
  environment: RuntimeEnvironment = process.env,
): boolean {
  return (
    environment.NODE_ENV !== "production" &&
    environment.LUNAR_FORGE_AUTH_E2E_MODE === "playwright"
  );
}

export function getE2EIdentity(value: string | undefined): AuthIdentity | null {
  if (value === "user") {
    return {
      id: "user-e2e",
      email: "user@example.test",
      assuranceLevel: "aal1",
    };
  }

  if (value === "admin-aal1" || value === "admin-aal2") {
    return {
      id: "admin-e2e",
      email: "admin@example.test",
      assuranceLevel: value === "admin-aal2" ? "aal2" : "aal1",
    };
  }

  return null;
}
