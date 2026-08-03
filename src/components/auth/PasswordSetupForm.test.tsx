import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createBrowserSupabaseClient } from "@/lib/auth/client";

import { PasswordSetupForm } from "./PasswordSetupForm";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));
vi.mock("@/lib/auth/client", () => ({
  createBrowserSupabaseClient: vi.fn(),
}));

const replace = vi.fn();
const refresh = vi.fn();
const updateUser = vi.fn();

describe("PasswordSetupForm", () => {
  beforeEach(() => {
    vi.mocked(useRouter).mockReturnValue({ replace, refresh } as never);
    vi.mocked(createBrowserSupabaseClient).mockReturnValue({
      auth: { updateUser },
    } as never);
  });

  it("keeps an invite incomplete when passwords do not match", async () => {
    const user = userEvent.setup();
    render(<PasswordSetupForm />);

    await user.type(screen.getByLabelText("New password"), "a-long-password");
    await user.type(screen.getByLabelText("Confirm password"), "another-password");
    await user.click(screen.getByRole("button", { name: "Set password" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("sets the invited user's password and enters the sandbox", async () => {
    updateUser.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    render(<PasswordSetupForm />);

    await user.type(screen.getByLabelText("New password"), "a-long-password");
    await user.type(screen.getByLabelText("Confirm password"), "a-long-password");
    await user.click(screen.getByRole("button", { name: "Set password" }));

    expect(updateUser).toHaveBeenCalledWith({ password: "a-long-password" });
    expect(replace).toHaveBeenCalledWith("/sandbox");
  });
});
