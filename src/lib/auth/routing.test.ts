import { describe, expect, it } from "vitest";

import {
  decideRouteAccess,
  isProtectedPath,
  safeNextPath,
  type AuthIdentity,
} from "./routing";

const user: AuthIdentity = {
  id: "user-1",
  email: "user@example.test",
  assuranceLevel: "aal1",
};
const adminAal1: AuthIdentity = { ...user, id: "admin-1" };
const adminAal2: AuthIdentity = {
  ...adminAal1,
  assuranceLevel: "aal2",
};
const admins = new Set(["admin-1"]);
const nobody = new Set<string>();

describe("auth route decisions", () => {
  it("keeps product, docs, login, and policy routes public", () => {
    for (const pathname of [
      "/",
      "/docs",
      "/docs/security-model",
      "/compare",
      "/design-system",
      "/login",
      "/privacy",
      "/security",
      "/terms",
    ]) {
      expect(isProtectedPath(pathname)).toBe(false);
      expect(decideRouteAccess(pathname, null, admins, nobody)).toEqual({
        kind: "allow",
      });
    }
  });

  it("requires identity for sandbox and admin routes", () => {
    expect(decideRouteAccess("/sandbox", null, admins, nobody)).toEqual({
      kind: "login",
    });
    expect(decideRouteAccess("/admin", null, admins, nobody)).toEqual({
      kind: "login",
    });
  });

  it("allows invited users into sandbox but not admin", () => {
    expect(decideRouteAccess("/sandbox", user, admins, nobody)).toEqual({
      kind: "allow",
    });
    expect(decideRouteAccess("/admin", user, admins, nobody)).toEqual({
      kind: "sandbox",
      error: "admin_required",
    });
  });

  it("requires aal2 for admins", () => {
    expect(decideRouteAccess("/admin", adminAal1, admins, nobody)).toEqual({
      kind: "mfa",
    });
    expect(decideRouteAccess("/admin", adminAal2, admins, nobody)).toEqual({
      kind: "allow",
    });
  });

  it("denies suspended users from every protected surface", () => {
    expect(
      decideRouteAccess("/sandbox", user, admins, new Set([user.id])),
    ).toEqual({ kind: "login", error: "account_suspended" });
  });

  it("rejects external and protocol-relative post-auth destinations", () => {
    expect(safeNextPath("https://evil.example", "/admin")).toBe("/admin");
    expect(safeNextPath("//evil.example", "/admin")).toBe("/admin");
    expect(safeNextPath("/admin?tab=usage", "/sandbox")).toBe(
      "/admin?tab=usage",
    );
  });
});
