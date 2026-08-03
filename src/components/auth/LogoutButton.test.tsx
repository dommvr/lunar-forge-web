import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LogoutButton } from "./LogoutButton";

describe("LogoutButton", () => {
  it("uses a POST form for logout", () => {
    render(<LogoutButton />);

    const button = screen.getByRole("button", { name: "Sign out" });
    const form = button.closest("form");
    expect(form).toHaveAttribute("action", "/auth/logout");
    expect(form).toHaveAttribute("method", "post");
  });
});
