import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePathname } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SiteNav } from "./SiteNav";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

describe("SiteNav", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue("/docs/permissions-and-approvals");
  });

  it("marks the current route active", () => {
    render(<SiteNav />);

    expect(screen.getByRole("link", { name: "Docs" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("opens the mobile menu and returns focus on Escape", async () => {
    const user = userEvent.setup();
    render(<SiteNav />);
    const toggle = screen.getByRole("button", { name: "Open menu" });

    await user.click(toggle);

    const menu = screen.getByRole("navigation", { name: "Mobile" });
    expect(within(menu).getByRole("link", { name: "Docs" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.keyboard("{Escape}");

    expect(
      screen.queryByRole("navigation", { name: "Mobile" }),
    ).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });
});
