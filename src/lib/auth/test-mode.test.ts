import { describe, expect, it } from "vitest";

import { getE2EIdentity, isAuthE2EMode } from "./test-mode";

describe("auth E2E mode", () => {
  it("cannot be enabled in production", () => {
    expect(
      isAuthE2EMode({
        NODE_ENV: "production",
        LUNAR_FORGE_AUTH_E2E_MODE: "playwright",
      }),
    ).toBe(false);
  });

  it("maps only explicit fake identities", () => {
    expect(getE2EIdentity("admin-aal2")).toMatchObject({
      id: "admin-e2e",
      assuranceLevel: "aal2",
    });
    expect(getE2EIdentity("unknown")).toBeNull();
  });
});
