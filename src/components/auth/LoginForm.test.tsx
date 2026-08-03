import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createBrowserSupabaseClient } from "@/lib/auth/client";

import { LoginForm } from "./LoginForm";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));
vi.mock("@/lib/auth/client", () => ({
  createBrowserSupabaseClient: vi.fn(),
}));

const replace = vi.fn();
const refresh = vi.fn();
const signInWithPassword = vi.fn();

describe("LoginForm", () => {
  beforeEach(() => {
    vi.mocked(useRouter).mockReturnValue({ replace, refresh } as never);
    vi.mocked(createBrowserSupabaseClient).mockReturnValue({
      auth: { signInWithPassword },
    } as never);
  });

  it("shows a bounded login error without exposing provider details", async () => {
    signInWithPassword.mockResolvedValue({
      error: new Error("provider internals"),
    });
    const user = userEvent.setup();
    render(<LoginForm nextPath="/sandbox" />);

    await user.type(screen.getByLabelText("Email"), "invited@example.test");
    await user.type(screen.getByLabelText("Password"), "incorrect-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Email or password was not accepted.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("provider internals");
  });

  it("continues to the protected destination after password login", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    render(<LoginForm nextPath="/admin" />);

    await user.type(screen.getByLabelText("Email"), "owner@example.test");
    await user.type(screen.getByLabelText("Password"), "a-secure-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: "owner@example.test",
      password: "a-secure-password",
    });
    expect(replace).toHaveBeenCalledWith("/admin");
    expect(refresh).toHaveBeenCalled();
  });
});
