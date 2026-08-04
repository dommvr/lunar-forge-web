import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SandboxApi } from "@/lib/api/client";
import type { AgentEvent } from "@/lib/api/generated/client";
import type { RealtimeClientOptions } from "@/lib/realtime";

import { SandboxApp } from "./SandboxApp";
import type { RealtimeFactory } from "./hooks/useSandboxSession";

const now = "2026-01-01T00:00:00Z";
const expiresAt = "2099-01-01T00:30:00Z";

function event(
  sequence: number,
  type: string,
  payload: Record<string, unknown> = {},
): AgentEvent {
  return {
    schema_version: 1,
    event_id: `evt-${sequence}`,
    session_id: "session-a",
    turn_id: "turn-a",
    sequence,
    timestamp: now,
    type,
    payload,
    parent_event_id: null,
  };
}

function sandboxHarness() {
  let realtimeOptions: RealtimeClientOptions | undefined;
  const emit = (item: AgentEvent) => realtimeOptions?.onEvent(item);
  const apiMock = {
    listSandboxes: vi.fn(async () => ({ items: [] })),
    createSandbox: vi.fn(async () => ({
      id: "sandbox-a",
      owner_id: "user-a",
      template_id: "vite-react",
      runtime_provider: "fake",
      runtime_reference: "runtime-a",
      status: "ready",
      created_at: now,
      last_activity_at: now,
      expires_at: expiresAt,
    })),
    getSandbox: vi.fn(async () => ({
      id: "sandbox-a",
      owner_id: "user-a",
      template_id: "vite-react",
      runtime_provider: "fake",
      runtime_reference: "runtime-a",
      status: "ready",
      created_at: now,
      last_activity_at: now,
      expires_at: expiresAt,
    })),
    createSession: vi.fn(async () => ({
      id: "session-a",
      sandbox_id: "sandbox-a",
      owner_id: "user-a",
      status: "active",
      created_at: now,
      last_sequence: 0,
      compacted_summary_count: 0,
    })),
    createTurn: vi.fn(async () => {
      emit(event(2, "turn.started"));
      emit(
        event(3, "permission.requested", {
          request_id: "approval-a",
          description: "Run validation without network access.",
          details: "npm run validate",
          risk: "medium",
        }),
      );
      return {
        id: "turn-a",
        session_id: "session-a",
        owner_id: "user-a",
        status: "waiting_for_approval",
        created_at: now,
        started_at: now,
        finished_at: null,
      };
    }),
    resolveApproval: vi.fn(async (_sessionId, _approvalId, body) => {
      emit(event(4, "permission.resolved", { allowed: body.approved }));
      if (body.approved) {
        emit(event(5, "validation.started", { step_count: 5 }));
        emit(event(6, "validation.finished", { status: "passed" }));
        emit(event(7, "turn.finished", { status: "completed" }));
      } else {
        emit(event(5, "turn.cancelled", { status: "cancelled" }));
      }
      return {
        id: "approval-a",
        sandbox_id: "sandbox-a",
        session_id: "session-a",
        turn_id: "turn-a",
        owner_id: "user-a",
        kind: "command.run",
        title: "Run command in sandbox",
        summary: "Run validation",
        details: "npm run validate",
        risk: "medium",
        status: body.approved ? "approved" : "denied",
        expires_at: expiresAt,
      };
    }),
    cancelTurn: vi.fn(async () => {
      emit(event(4, "turn.cancelled", { status: "cancelled" }));
      emit(
        event(5, "rollback.finished", {
          status: "completed",
          restored_files: ["app/page.tsx", "package.json"],
          removed_files: ["components/Pricing.tsx"],
          skipped_files: [],
          errors: [],
        }),
      );
      return {
        turn: {
          id: "turn-a",
          session_id: "session-a",
          owner_id: "user-a",
          status: "cancelled",
          created_at: now,
          started_at: now,
          finished_at: now,
        },
        rollback_report: "Files restored.",
      };
    }),
    compactSession: vi.fn(async () => {
      emit(event(2, "memory.compaction.finished", { status: "completed" }));
      return {
        compacted: true,
        summary: "Compacted",
        session: {
          id: "session-a",
          sandbox_id: "sandbox-a",
          owner_id: "user-a",
          status: "active",
          created_at: now,
          last_sequence: 2,
          compacted_summary_count: 1,
        },
      };
    }),
    resetSandbox: vi.fn(async () => ({
      id: "sandbox-a",
      owner_id: "user-a",
      template_id: "vite-react",
      runtime_provider: "fake",
      runtime_reference: "runtime-a",
      status: "ready",
      created_at: now,
      last_activity_at: now,
      expires_at: expiresAt,
    })),
    deleteSandbox: vi.fn(),
    replayEvents: vi.fn(),
    listFiles: vi.fn(async () => ({
      sandbox_id: "sandbox-a",
      items: [],
      truncated: false,
    })),
    listArtifacts: vi.fn(async () => ({ items: [] })),
    createRealtimeTicket: vi.fn(),
  };
  const api = apiMock as unknown as SandboxApi;
  const realtimeFactory: RealtimeFactory = (options) => ({
    start() {
      realtimeOptions = options;
      options.onConnectionState("connected", 0);
      options.onEvent(event(1, "session.started", { status: "ready" }));
    },
    stop() {},
  });
  return { api, apiMock, realtimeFactory };
}

describe("SandboxApp", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("moves focus to Deny when a server approval opens", async () => {
    const user = userEvent.setup();
    const harness = sandboxHarness();
    render(<SandboxApp {...harness} />);
    await screen.findByText("private runtime is ready", { exact: false });

    await user.click(
      screen.getByRole("button", { name: /Add a responsive pricing section/ }),
    );

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Waiting for approval",
      ),
    );
    expect(screen.getAllByRole("button", { name: "Deny" })[0]).toHaveFocus();
    expect(screen.getByLabelText("Message LunarForge")).toBeDisabled();
  });

  it("moves mobile-sheet focus to Deny when the approval opens", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    const user = userEvent.setup();
    render(<SandboxApp {...sandboxHarness()} />);
    await screen.findByText("private runtime is ready", { exact: false });

    await user.click(
      screen.getByRole("button", { name: /Add a responsive pricing section/ }),
    );

    await waitFor(() => {
      const denials = screen.getAllByRole("button", { name: "Deny" });
      expect(denials.at(-1)).toHaveFocus();
    });
    vi.unstubAllGlobals();
  });

  it("switches the mobile segmented panels", async () => {
    const user = userEvent.setup();
    render(<SandboxApp {...sandboxHarness()} />);
    await screen.findByText("private runtime is ready", { exact: false });

    const chatTab = screen.getByRole("tab", { name: "Chat" });
    const filesTab = screen.getByRole("tab", { name: "Files" });
    const eventsTab = screen.getByRole("tab", { name: "Events" });
    expect(chatTab).toHaveAttribute("aria-selected", "true");

    await user.click(filesTab);
    expect(filesTab).toHaveAttribute("aria-selected", "true");
    expect(
      within(screen.getByTestId("mobile-panel")).getByLabelText("Project files"),
    ).toBeInTheDocument();

    await user.click(eventsTab);
    expect(eventsTab).toHaveAttribute("aria-selected", "true");
    expect(
      within(screen.getByTestId("mobile-panel")).getByLabelText("Session details"),
    ).toBeInTheDocument();
  });

  it("sends BYOK only with a turn and keeps it out of browser storage", async () => {
    const user = userEvent.setup();
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const harness = sandboxHarness();
    const { unmount } = render(<SandboxApp {...harness} />);
    await screen.findByText("private runtime is ready", { exact: false });

    await user.click(screen.getByLabelText(/Bring your own key/));
    const keyInput = screen.getByLabelText("Provider key");
    await user.type(keyInput, "sk-memory-only-secret");
    await user.selectOptions(screen.getByLabelText("BYOK provider"), "anthropic");
    await user.click(
      screen.getByRole("button", { name: /Explain this project/ }),
    );

    expect(storage).not.toHaveBeenCalled();
    expect(harness.apiMock.createTurn).toHaveBeenCalledWith(
      "session-a",
      expect.objectContaining({
        settings: expect.objectContaining({
          funding_mode: "byok",
          provider: "anthropic",
        }),
        provider_api_key: "sk-memory-only-secret",
      }),
    );

    unmount();
    render(<SandboxApp {...sandboxHarness()} />);
    await screen.findByText("private runtime is ready", { exact: false });
    await user.click(screen.getByLabelText(/Bring your own key/));
    expect(screen.getByLabelText("Provider key")).toHaveValue("");
  });
});
