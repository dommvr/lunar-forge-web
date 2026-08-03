import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommandMenu } from "./CommandMenu";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(),
}));

function Harness() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button">Menu opener</button>
      <CommandMenu open={open} onOpenChange={setOpen} />
    </>
  );
}

describe("CommandMenu", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(useRouter).mockReturnValue({ push } as never);
  });

  it("opens with Ctrl-K, navigates with arrows, and restores focus on Escape", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Menu opener" });
    opener.focus();

    await user.keyboard("{Control>}k{/Control}");

    const input = screen.getByRole("textbox", { name: "Search documentation" });
    expect(input).toHaveFocus();

    await user.keyboard("{ArrowDown}{Enter}");
    expect(push).toHaveBeenCalledWith("/docs/quick-start");

    opener.focus();
    await user.keyboard("{Control>}k{/Control}");
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
