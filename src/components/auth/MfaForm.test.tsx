import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createBrowserSupabaseClient } from "@/lib/auth/client";

import { MfaForm } from "./MfaForm";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));
vi.mock("@/lib/auth/client", () => ({
  createBrowserSupabaseClient: vi.fn(),
}));

const replace = vi.fn();
const refresh = vi.fn();
const getAuthenticatorAssuranceLevel = vi.fn();
const listFactors = vi.fn();
const enroll = vi.fn();
const challengeAndVerify = vi.fn();

describe("MfaForm", () => {
  beforeEach(() => {
    vi.mocked(useRouter).mockReturnValue({ replace, refresh } as never);
    vi.mocked(createBrowserSupabaseClient).mockReturnValue({
      auth: {
        mfa: {
          getAuthenticatorAssuranceLevel,
          listFactors,
          enroll,
          challengeAndVerify,
        },
      },
    } as never);
    getAuthenticatorAssuranceLevel.mockResolvedValue({
      data: { currentLevel: "aal1", nextLevel: "aal2" },
    });
    listFactors.mockResolvedValue({
      data: {
        totp: [{ id: "factor-1", status: "verified" }],
        phone: [],
      },
      error: null,
    });
  });

  it("challenges an enrolled admin factor before continuing", async () => {
    challengeAndVerify.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    render(<MfaForm nextPath="/admin" />);

    const code = await screen.findByLabelText("Verification code");
    await user.type(code, "123456");
    await user.click(
      screen.getByRole("button", { name: "Verify and continue" }),
    );

    expect(challengeAndVerify).toHaveBeenCalledWith({
      factorId: "factor-1",
      code: "123456",
    });
    expect(replace).toHaveBeenCalledWith("/admin");
    expect(refresh).toHaveBeenCalled();
  });

  it("starts enrollment when the admin has no verified TOTP factor", async () => {
    listFactors.mockResolvedValue({
      data: { totp: [], phone: [] },
      error: null,
    });
    enroll.mockResolvedValue({
      data: {
        id: "new-factor",
        totp: {
          qr_code: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E",
          secret: "TEST-SECRET",
        },
      },
      error: null,
    });

    render(<MfaForm />);

    await waitFor(() => expect(enroll).toHaveBeenCalled());
    expect(
      screen.getByAltText("Authenticator enrollment QR code"),
    ).toBeInTheDocument();
    expect(screen.getByText("Enter a setup key instead")).toBeInTheDocument();
  });
});
