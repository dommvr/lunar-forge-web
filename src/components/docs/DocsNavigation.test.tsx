import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { usePathname } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocsSidebar } from "./DocsSidebar";
import { DocsToc } from "./DocsToc";
import { DocsBar } from "./DocsBar";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

describe("DocsSidebar", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue(
      "/docs/permissions-and-approvals",
    );
  });

  it("marks and scrolls the current item into view", () => {
    const scrollIntoView = vi.spyOn(Element.prototype, "scrollIntoView");

    render(<DocsSidebar />);

    expect(
      screen.getByRole("link", { name: "Permissions and approvals" }),
    ).toHaveAttribute("aria-current", "page");
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest" });
  });
});

describe("DocsBar", () => {
  beforeEach(() => {
    vi.mocked(usePathname).mockReturnValue("/docs/permissions-and-approvals");
  });

  it("opens the mobile drawer, marks the route, and returns focus on Escape", async () => {
    const user = userEvent.setup();
    render(<DocsBar section="Execution" page="Permissions and approvals" />);
    const trigger = screen.getByRole("button", {
      name: "Open documentation navigation",
    });

    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "Documentation navigation" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Permissions and approvals" }),
    ).toHaveAttribute("aria-current", "page");

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});

describe("DocsToc", () => {
  it("updates the active anchor from heading intersections", () => {
    let notify: IntersectionObserverCallback | undefined;

    class TestIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        notify = callback;
      }

      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
      readonly root = null;
      readonly rootMargin = "";
      readonly thresholds = [0];
    }

    vi.stubGlobal("IntersectionObserver", TestIntersectionObserver);

    render(
      <>
        <h2 id="overview">Overview</h2>
        <h2 id="configuration">Configuration</h2>
        <DocsToc
          entries={[
            { id: "overview", title: "Overview", level: 0 },
            { id: "configuration", title: "Configuration", level: 0 },
          ]}
        />
      </>,
    );

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute(
      "aria-current",
      "location",
    );

    const target = document.getElementById("configuration");
    act(() => {
      notify?.(
        [
          {
            target,
            isIntersecting: true,
            boundingClientRect: { top: 120 },
          } as unknown as IntersectionObserverEntry,
        ],
        {} as IntersectionObserver,
      );
    });

    expect(
      screen.getByRole("link", { name: "Configuration" }),
    ).toHaveAttribute("aria-current", "location");
  });
});
