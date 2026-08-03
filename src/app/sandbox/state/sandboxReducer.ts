import type { AgentEvent, ArtifactResponse } from "@/lib/api/generated/client";
import type { ActivityEvent } from "@/lib/sandbox";

export type SandboxPhase =
  | "idle"
  | "provisioning"
  | "ready"
  | "running"
  | "gated"
  | "validating"
  | "done"
  | "cancelled"
  | "expired"
  | "limited"
  | "offline"
  | "error"
  | "fatal";

export type SandboxMessage = {
  id: string;
  role: "user" | "agent";
  text: string;
};

export type PendingApproval = {
  id: string;
  title: string;
  summary: string;
  details: string;
  risk: "low" | "medium" | "high";
};

export type SandboxClientState = {
  phase: SandboxPhase;
  phaseBeforeOffline: SandboxPhase;
  sandboxId?: string;
  sessionId?: string;
  lastSequence: number;
  seenEventIds: readonly string[];
  reconnectAttempt: number;
  messages: readonly SandboxMessage[];
  activities: readonly ActivityEvent[];
  visibleTools: number;
  progress: string | null;
  checksDone: number;
  changed: boolean;
  approval: PendingApproval | null;
  artifacts: readonly ArtifactResponse[];
  rollbackReport: string | null;
  compactionSummary: string | null;
  errorMessage: string | null;
};

export const initialSandboxState: SandboxClientState = {
  phase: "idle",
  phaseBeforeOffline: "idle",
  lastSequence: 0,
  seenEventIds: [],
  reconnectAttempt: 0,
  messages: [],
  activities: [],
  visibleTools: 0,
  progress: null,
  checksDone: 0,
  changed: false,
  approval: null,
  artifacts: [],
  rollbackReport: null,
  compactionSummary: null,
  errorMessage: null,
};

export type SandboxAction =
  | { type: "provision" }
  | { type: "ready"; sandboxId: string; sessionId: string }
  | { type: "user.message"; id: string; text: string }
  | { type: "event"; event: AgentEvent }
  | {
      type: "connection";
      state: "connecting" | "connected" | "offline" | "fatal";
      attempt: number;
    }
  | { type: "artifacts"; artifacts: readonly ArtifactResponse[] }
  | { type: "files"; changed: boolean }
  | { type: "api.error"; message: string; fatal?: boolean; limited?: boolean }
  | { type: "reset" };

function payload(event: AgentEvent): Record<string, unknown> {
  return event.payload as Record<string, unknown>;
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function eventActivity(event: AgentEvent): ActivityEvent {
  const data = payload(event);
  const detail =
    text(data.message) ||
    text(data.description) ||
    text(data.tool_name) ||
    text(data.status) ||
    text(data.reason) ||
    text(data.text) ||
    "event received";
  return {
    name: event.type,
    detail: detail.slice(0, 120),
    time: `#${event.sequence}`,
    tone:
      event.type.endsWith("finished") ||
      event.type === "permission.resolved" ||
      event.type === "session.started"
        ? "success"
        : "muted",
  };
}

function rollbackText(data: Record<string, unknown>): string {
  const restored = Array.isArray(data.restored_files)
    ? data.restored_files.filter((item): item is string => typeof item === "string")
    : [];
  const removed = Array.isArray(data.removed_files)
    ? data.removed_files.filter((item): item is string => typeof item === "string")
    : [];
  const pieces = [
    removed.length ? `${removed.join(", ")} removed` : "",
    restored.length ? `${restored.join(", ")} restored` : "",
  ].filter(Boolean);
  return pieces.length
    ? `Task stopped. ${pieces.join("; ")}.`
    : "Task stopped. No current-turn file changes required rollback.";
}

export function sandboxReducer(
  state: SandboxClientState,
  action: SandboxAction,
): SandboxClientState {
  switch (action.type) {
    case "provision":
      return { ...initialSandboxState, phase: "provisioning" };
    case "ready":
      return {
        ...initialSandboxState,
        phase: "ready",
        phaseBeforeOffline: "ready",
        sandboxId: action.sandboxId,
        sessionId: action.sessionId,
      };
    case "user.message":
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: action.id, role: "user", text: action.text },
        ],
        rollbackReport: null,
        compactionSummary: null,
      };
    case "artifacts":
      return { ...state, artifacts: action.artifacts };
    case "files":
      return { ...state, changed: action.changed };
    case "connection": {
      if (action.state === "offline") {
        return {
          ...state,
          phase: "offline",
          phaseBeforeOffline:
            state.phase === "offline" ? state.phaseBeforeOffline : state.phase,
          reconnectAttempt: action.attempt,
        };
      }
      if (action.state === "fatal") {
        return {
          ...state,
          phase: "fatal",
          reconnectAttempt: action.attempt,
          errorMessage: "The event stream could not be recovered.",
        };
      }
      if (action.state === "connected" && state.phase === "offline") {
        return {
          ...state,
          phase: state.phaseBeforeOffline,
          reconnectAttempt: 0,
        };
      }
      return { ...state, reconnectAttempt: action.attempt };
    }
    case "api.error":
      return {
        ...state,
        phase: action.limited ? "limited" : action.fatal ? "fatal" : "error",
        errorMessage: action.message,
        progress: null,
      };
    case "reset":
      return initialSandboxState;
    case "event": {
      const event = action.event;
      if (
        event.sequence <= state.lastSequence ||
        state.seenEventIds.includes(event.event_id)
      ) {
        return state;
      }
      const data = payload(event);
      const next: SandboxClientState = {
        ...state,
        lastSequence: event.sequence,
        seenEventIds: [...state.seenEventIds.slice(-499), event.event_id],
        activities: [...state.activities, eventActivity(event)].slice(-500),
      };

      switch (event.type) {
        case "session.started":
          return { ...next, phase: "ready", phaseBeforeOffline: "ready" };
        case "turn.started":
          return {
            ...next,
            phase: "running",
            phaseBeforeOffline: "running",
            visibleTools: 0,
            checksDone: 0,
            approval: null,
            progress: "Starting turn",
            errorMessage: null,
          };
        case "status.updated":
          return {
            ...next,
            progress: text(data.message, "Working"),
          };
        case "tool.started":
          return {
            ...next,
            visibleTools: Math.min(4, next.visibleTools + 1),
            progress: text(data.tool_name, "Running tool"),
          };
        case "tool.finished":
          return {
            ...next,
            changed:
              next.changed ||
              (Array.isArray(data.changed_files) && data.changed_files.length > 0),
          };
        case "assistant.message.completed": {
          const message = text(data.text);
          if (!message) return next;
          return {
            ...next,
            messages: [
              ...next.messages,
              { id: event.event_id, role: "agent", text: message },
            ],
          };
        }
        case "permission.requested":
          return {
            ...next,
            phase: "gated",
            phaseBeforeOffline: "gated",
            progress: null,
            approval: {
              id: text(data.request_id, text(data.id)),
              title: "Run command in sandbox",
              summary: text(data.description, "Approval is required."),
              details: text(data.details, "Command details unavailable."),
              risk:
                data.risk === "low" || data.risk === "high" ? data.risk : "medium",
            },
          };
        case "permission.resolved":
          return {
            ...next,
            phase: data.allowed === true ? "validating" : next.phase,
            phaseBeforeOffline:
              data.allowed === true ? "validating" : next.phaseBeforeOffline,
            approval: null,
          };
        case "validation.started":
          return {
            ...next,
            phase: "validating",
            phaseBeforeOffline: "validating",
            checksDone: 0,
            progress: "Running validation · step 1 of 5",
          };
        case "validation.finished":
          return {
            ...next,
            phase: data.status === "passed" ? "validating" : "error",
            checksDone: data.status === "passed" ? 5 : next.checksDone,
            progress: data.status === "passed" ? "Validation passed" : null,
            errorMessage:
              data.status === "passed" ? null : "Project validation failed.",
          };
        case "turn.finished":
          return {
            ...next,
            phase: "done",
            phaseBeforeOffline: "done",
            progress: null,
            approval: null,
            changed: true,
          };
        case "turn.cancelled":
          return {
            ...next,
            phase: "cancelled",
            phaseBeforeOffline: "cancelled",
            progress: null,
            approval: null,
          };
        case "rollback.finished": {
          const report = rollbackText(data);
          return {
            ...next,
            phase: "cancelled",
            phaseBeforeOffline: "cancelled",
            changed: data.status !== "completed",
            rollbackReport: report,
            messages: [
              ...next.messages,
              { id: event.event_id, role: "agent", text: report },
            ],
          };
        }
        case "memory.compaction.finished": {
          const summary =
            data.status === "completed"
              ? "Older context compacted into a safe public summary."
              : text(data.warning, "Context compaction did not complete.");
          return {
            ...next,
            compactionSummary: summary,
            messages: [
              ...next.messages,
              { id: event.event_id, role: "agent", text: summary },
            ],
          };
        }
        case "sandbox.expired":
          return {
            ...next,
            phase: "expired",
            phaseBeforeOffline: "expired",
            progress: null,
          };
        case "quota.limited":
          return {
            ...next,
            phase: "limited",
            phaseBeforeOffline: "limited",
            errorMessage: text(data.message, "Sandbox usage limit reached."),
            progress: null,
          };
        case "error":
          return {
            ...next,
            phase: data.fatal === true ? "fatal" : "error",
            errorMessage: text(data.message, "The turn could not continue."),
            progress: null,
          };
        default:
          return next;
      }
    }
  }
}
