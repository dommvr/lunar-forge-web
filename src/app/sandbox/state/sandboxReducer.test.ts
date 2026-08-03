import { describe, expect, it } from "vitest";

import type { AgentEvent } from "@/lib/api/generated/client";

import { initialSandboxState, sandboxReducer } from "./sandboxReducer";

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
    timestamp: "2026-01-01T00:00:00Z",
    type,
    payload,
    parent_event_id: null,
  };
}

describe("sandboxReducer", () => {
  it("maps ordered events through running, gated, validating, and done", () => {
    let state = sandboxReducer(initialSandboxState, {
      type: "ready",
      sandboxId: "sandbox-a",
      sessionId: "session-a",
    });
    state = sandboxReducer(state, { type: "event", event: event(1, "turn.started") });
    expect(state.phase).toBe("running");

    state = sandboxReducer(state, {
      type: "event",
      event: event(2, "permission.requested", {
        request_id: "approval-a",
        description: "Run validation",
        details: "npm run validate",
        risk: "medium",
      }),
    });
    expect(state.phase).toBe("gated");
    expect(state.approval?.id).toBe("approval-a");

    state = sandboxReducer(state, {
      type: "event",
      event: event(3, "permission.resolved", { allowed: true }),
    });
    expect(state.phase).toBe("validating");

    state = sandboxReducer(state, {
      type: "event",
      event: event(4, "validation.finished", { status: "passed" }),
    });
    state = sandboxReducer(state, {
      type: "event",
      event: event(5, "turn.finished", { status: "completed" }),
    });
    expect(state.phase).toBe("done");
    expect(state.checksDone).toBe(5);
  });

  it("ignores duplicate and out-of-order replayed events", () => {
    const first = sandboxReducer(initialSandboxState, {
      type: "event",
      event: event(1, "turn.started"),
    });
    const duplicate = sandboxReducer(first, {
      type: "event",
      event: event(1, "turn.finished"),
    });
    expect(duplicate).toBe(first);
    expect(duplicate.phase).toBe("running");
  });

  it("renders cancellation only after the confirmed rollback report", () => {
    let state = sandboxReducer(initialSandboxState, {
      type: "event",
      event: event(1, "turn.cancelled", { status: "cancelled" }),
    });
    expect(state.phase).toBe("cancelled");
    expect(state.rollbackReport).toBeNull();

    state = sandboxReducer(state, {
      type: "event",
      event: event(2, "rollback.finished", {
        status: "completed",
        restored_files: ["app/page.tsx", "package.json"],
        removed_files: ["components/Pricing.tsx"],
        skipped_files: [],
        errors: [],
      }),
    });
    expect(state.rollbackReport).toContain("Pricing.tsx removed");
    expect(state.rollbackReport).toContain("app/page.tsx, package.json restored");
    expect(state.changed).toBe(false);
  });

  it("maps compaction and reconnect without losing the prior phase", () => {
    let state = sandboxReducer(initialSandboxState, {
      type: "event",
      event: event(1, "turn.finished", { status: "completed" }),
    });
    state = sandboxReducer(state, {
      type: "connection",
      state: "offline",
      attempt: 2,
    });
    expect(state.phase).toBe("offline");
    state = sandboxReducer(state, {
      type: "connection",
      state: "connected",
      attempt: 0,
    });
    expect(state.phase).toBe("done");

    state = sandboxReducer(state, {
      type: "event",
      event: event(2, "memory.compaction.finished", { status: "completed" }),
    });
    expect(state.compactionSummary).toContain("safe public summary");
  });

  it("exposes limited, recoverable, fatal, and expired-compatible phases", () => {
    expect(
      sandboxReducer(initialSandboxState, {
        type: "api.error",
        message: "Limit reached",
        limited: true,
      }).phase,
    ).toBe("limited");
    expect(
      sandboxReducer(initialSandboxState, {
        type: "api.error",
        message: "Retry",
      }).phase,
    ).toBe("error");
    expect(
      sandboxReducer(initialSandboxState, {
        type: "api.error",
        message: "Stopped",
        fatal: true,
      }).phase,
    ).toBe("fatal");
    expect(
      sandboxReducer(initialSandboxState, {
        type: "event",
        event: event(1, "sandbox.expired"),
      }).phase,
    ).toBe("expired");
  });
});
