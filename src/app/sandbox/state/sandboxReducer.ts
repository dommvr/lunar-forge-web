import type {
  AgentEvent,
  ArtifactResponse,
  FileContentResponse,
  FilesResponse,
} from "@/lib/api/generated/client";
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
  streaming?: boolean;
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
  runtimeProvider?: string;
  expiresAt?: string;
  lastSequence: number;
  seenEventIds: readonly string[];
  reconnectAttempt: number;
  messages: readonly SandboxMessage[];
  streamingMessageId: string | null;
  activities: readonly ActivityEvent[];
  visibleTools: number;
  progress: string | null;
  checksDone: number;
  changed: boolean;
  changedPaths: readonly string[];
  turnChangedPaths: readonly string[];
  preTurnChangedPaths: readonly string[];
  fileRevision: number;
  files: FilesResponse | null;
  selectedFile: FileContentResponse | null;
  validationMessage: string | null;
  approval: PendingApproval | null;
  artifacts: readonly ArtifactResponse[];
  usageInputTokens: number;
  usageOutputTokens: number;
  usageEstimatedCost: number;
  rollbackReport: string | null;
  compactionSummary: string | null;
  errorCode: string | null;
  errorMessage: string | null;
};

export const initialSandboxState: SandboxClientState = {
  phase: "idle",
  phaseBeforeOffline: "idle",
  lastSequence: 0,
  seenEventIds: [],
  reconnectAttempt: 0,
  messages: [],
  streamingMessageId: null,
  activities: [],
  visibleTools: 0,
  progress: null,
  checksDone: 0,
  changed: false,
  changedPaths: [],
  turnChangedPaths: [],
  preTurnChangedPaths: [],
  fileRevision: 0,
  files: null,
  selectedFile: null,
  validationMessage: null,
  approval: null,
  artifacts: [],
  usageInputTokens: 0,
  usageOutputTokens: 0,
  usageEstimatedCost: 0,
  rollbackReport: null,
  compactionSummary: null,
  errorCode: null,
  errorMessage: null,
};

export type SandboxAction =
  | { type: "provision" }
  | {
      type: "ready";
      sandboxId: string;
      sessionId: string;
      runtimeProvider: string;
      expiresAt: string;
    }
  | { type: "user.message"; id: string; text: string }
  | { type: "event"; event: AgentEvent }
  | {
      type: "connection";
      state: "connecting" | "connected" | "offline" | "fatal";
      attempt: number;
    }
  | { type: "artifacts"; artifacts: readonly ArtifactResponse[] }
  | { type: "files"; files: FilesResponse }
  | { type: "file.content"; file: FileContentResponse }
  | { type: "activity"; expiresAt: string }
  | { type: "expired" }
  | { type: "compaction.result"; compacted: boolean; summary: string }
  | {
      type: "api.error";
      code?: string;
      message: string;
      fatal?: boolean;
      limited?: boolean;
    }
  | { type: "reset" };

function payload(event: AgentEvent): Record<string, unknown> {
  return event.payload as Record<string, unknown>;
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function unique(values: readonly string[]): string[] {
  return [...new Set(values)];
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
  const status = text(data.status, "unknown");
  const restored = strings(data.restored_files);
  const removed = strings(data.removed_files);
  const retained = strings(data.retained_files);
  const failed = strings(data.failed_files);
  const pieces = [
    removed.length ? `${removed.join(", ")} removed` : "",
    restored.length ? `${restored.join(", ")} restored` : "",
    retained.length ? `${retained.join(", ")} retained` : "",
    failed.length ? `${failed.join(", ")} could not be reverted` : "",
  ].filter(Boolean);
  if (status === "completed") {
    return pieces.length
      ? `Rollback confirmed: ${pieces.join("; ")}.`
      : "Rollback confirmed: no current-turn file changes required rollback.";
  }
  if (status === "partial") {
    return `Rollback partially completed${pieces.length ? `: ${pieces.join("; ")}` : ""}.`;
  }
  return `Rollback could not be confirmed${pieces.length ? `: ${pieces.join("; ")}` : ""}.`;
}

const QUOTA_CODES = new Set([
  "owner_funded_turn_limit",
  "owner_funded_user_cost_limit",
  "owner_funded_global_cost_limit",
  "daily_turn_limit",
  "daily_user_cost_limit",
  "daily_global_cost_limit",
  "owner_funded_disabled",
  "global_kill_switch_enabled",
  "sandbox_kill_switch",
  "rate_limit_exceeded",
  "quota_exceeded",
]);

function publicError(code: string | undefined, message: string): string {
  if (code === "provider_authentication_failed") {
    return "The provider rejected this BYOK credential. Re-enter a valid key and try again.";
  }
  if (code === "provider_rate_limited") {
    return "The model provider is rate-limiting requests. Please retry shortly.";
  }
  if (code === "provider_error") {
    return "The model provider could not complete this turn.";
  }
  if (code === "sandbox_cleanup_failed") {
    return "Sandbox cleanup failed. The service will reconcile it; retry deletion or contact an administrator.";
  }
  if (code === "sandbox_expired") {
    return "This sandbox expired after 30 minutes of inactivity. Create a new sandbox to continue.";
  }
  return message;
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
        runtimeProvider: action.runtimeProvider,
        expiresAt: action.expiresAt,
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
        validationMessage: null,
      };
    case "artifacts":
      return { ...state, artifacts: action.artifacts };
    case "files": {
      const previous = state.files
        ? new Map(state.files.items.map((item) => [item.path, item]))
        : null;
      const discovered = previous
        ? action.files.items
            .filter((item) => {
              const prior = previous.get(item.path);
              return !prior || prior.kind !== item.kind || prior.size_bytes !== item.size_bytes;
            })
            .map((item) => item.path)
        : [];
      const changedPaths = unique([...state.changedPaths, ...discovered]);
      return {
        ...state,
        files: action.files,
        changed: state.changed || changedPaths.length > 0,
        changedPaths,
        selectedFile:
          state.selectedFile &&
          action.files.items.some(
            (item) => item.kind === "file" && item.path === state.selectedFile?.path,
          )
            ? state.selectedFile
            : null,
      };
    }
    case "file.content":
      return { ...state, selectedFile: action.file };
    case "activity":
      return { ...state, expiresAt: action.expiresAt };
    case "expired":
      return {
        ...state,
        phase: "expired",
        phaseBeforeOffline: "expired",
        progress: null,
      };
    case "compaction.result": {
      const summary = action.compacted
        ? action.summary || "Older context was compacted into a safe public summary."
        : action.summary || "No context needed compaction.";
      if (state.compactionSummary === summary) return state;
      return {
        ...state,
        compactionSummary: summary,
        messages: [
          ...state.messages,
          { id: `compaction-${state.lastSequence}`, role: "agent", text: summary },
        ],
      };
    }
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
          errorCode: "event_stream_unavailable",
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
    case "api.error": {
      const limited = action.limited || (action.code ? QUOTA_CODES.has(action.code) : false);
      const expired = action.code === "sandbox_expired";
      return {
        ...state,
        phase: expired ? "expired" : limited ? "limited" : action.fatal ? "fatal" : "error",
        errorCode: action.code ?? null,
        errorMessage: publicError(action.code, action.message),
        progress: null,
      };
    }
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
            validationMessage: null,
            preTurnChangedPaths: next.changedPaths,
            turnChangedPaths: [],
            streamingMessageId: null,
            errorCode: null,
            errorMessage: null,
          };
        case "status.updated":
          return { ...next, progress: text(data.message, "Working") };
        case "tool.started":
          return {
            ...next,
            visibleTools: Math.min(4, next.visibleTools + 1),
            progress: text(data.tool_name, "Running tool"),
          };
        case "tool.finished": {
          const changed = unique([
            ...next.turnChangedPaths,
            ...strings(data.changed_files),
            ...strings(data.changed_paths),
          ]);
          return {
            ...next,
            changed: next.changed || changed.length > 0,
            changedPaths: unique([...next.changedPaths, ...changed]),
            turnChangedPaths: changed,
            fileRevision: changed.length ? next.fileRevision + 1 : next.fileRevision,
          };
        }
        case "assistant.message.delta": {
          const delta = text(data.delta, text(data.text));
          if (!delta) return next;
          const id = next.streamingMessageId ?? `assistant-${event.event_id}`;
          const existing = next.messages.findIndex((message) => message.id === id);
          const messages = [...next.messages];
          if (existing >= 0) {
            messages[existing] = { ...messages[existing], text: messages[existing].text + delta };
          } else {
            messages.push({ id, role: "agent", text: delta, streaming: true });
          }
          return { ...next, messages, streamingMessageId: id };
        }
        case "assistant.message.completed": {
          const message = text(data.text);
          if (!message && !next.streamingMessageId) return next;
          if (next.streamingMessageId) {
            const messages = next.messages.map((item) =>
              item.id === next.streamingMessageId
                ? { ...item, text: message || item.text, streaming: false }
                : item,
            );
            return { ...next, messages, streamingMessageId: null };
          }
          return {
            ...next,
            messages: [...next.messages, { id: event.event_id, role: "agent", text: message }],
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
              title: text(data.title, "Run command in sandbox"),
              summary: text(data.description, text(data.summary, "Approval is required.")),
              details: text(data.details, "Command details unavailable."),
              risk: data.risk === "low" || data.risk === "high" ? data.risk : "medium",
            },
          };
        case "permission.resolved": {
          const allowed = data.allowed === true || data.approved === true;
          return {
            ...next,
            phase: allowed ? "validating" : next.phase,
            phaseBeforeOffline: allowed ? "validating" : next.phaseBeforeOffline,
            approval: null,
          };
        }
        case "validation.started":
          return {
            ...next,
            phase: "validating",
            phaseBeforeOffline: "validating",
            checksDone: 0,
            progress: "Running validation",
            validationMessage: text(data.message, "Validation is running."),
          };
        case "validation.finished": {
          const passed = data.ok === true || data.status === "passed";
          const validationMessage = passed
            ? text(data.message, "Validation passed.")
            : text(data.error, text(data.message, "Project validation failed."));
          return {
            ...next,
            phase: passed ? "validating" : "error",
            checksDone: passed ? 5 : next.checksDone,
            progress: passed ? "Validation passed" : null,
            validationMessage,
            errorCode: passed ? null : "validation_failed",
            errorMessage: passed ? null : validationMessage,
          };
        }
        case "model.usage":
          return {
            ...next,
            usageInputTokens: next.usageInputTokens + Number(data.input_tokens ?? 0),
            usageOutputTokens: next.usageOutputTokens + Number(data.output_tokens ?? 0),
            usageEstimatedCost:
              next.usageEstimatedCost + Number(data.estimated_cost_usd ?? data.cost_usd ?? 0),
          };
        case "turn.finished": {
          const status = text(data.status, "completed");
          if (status === "cancelled" || status === "canceled") {
            return {
              ...next,
              phase: "cancelled",
              phaseBeforeOffline: "cancelled",
              progress: null,
              approval: null,
            };
          }
          if (status !== "completed" && status !== "success") {
            return {
              ...next,
              phase: "error",
              phaseBeforeOffline: "error",
              progress: null,
              approval: null,
              errorCode: "turn_failed",
              errorMessage: text(data.message, "The turn did not complete."),
            };
          }
          return {
            ...next,
            phase: "done",
            phaseBeforeOffline: "done",
            progress: null,
            approval: null,
            changed: next.changed || next.turnChangedPaths.length > 0,
            changedPaths: unique([...next.changedPaths, ...next.turnChangedPaths]),
            fileRevision: next.turnChangedPaths.length ? next.fileRevision + 1 : next.fileRevision,
          };
        }
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
          const rollbackCompleted = text(data.status) === "completed";
          const reverted = unique([...strings(data.removed_files), ...strings(data.restored_files)]);
          const remainingTurnPaths = rollbackCompleted
            ? next.turnChangedPaths.filter((path) => !reverted.includes(path))
            : next.turnChangedPaths;
          const changedPaths = rollbackCompleted
            ? unique([...next.preTurnChangedPaths, ...remainingTurnPaths])
            : next.changedPaths;
          return {
            ...next,
            phase: "cancelled",
            phaseBeforeOffline: "cancelled",
            changedPaths,
            turnChangedPaths: remainingTurnPaths,
            changed: rollbackCompleted ? changedPaths.length > 0 : next.changed,
            fileRevision: next.fileRevision + 1,
            rollbackReport: report,
            messages: [...next.messages, { id: event.event_id, role: "agent", text: report }],
          };
        }
        case "memory.compaction.finished": {
          const compacted = data.status === "completed" || data.compacted === true;
          const summary = compacted
            ? text(data.summary, "Older context was compacted into a safe public summary.")
            : text(data.warning, text(data.summary, "No context needed compaction."));
          if (next.compactionSummary === summary) {
            return { ...next, compactionSummary: summary };
          }
          return {
            ...next,
            compactionSummary: summary,
            messages: [...next.messages, { id: event.event_id, role: "agent", text: summary }],
          };
        }
        case "sandbox.expired":
          return { ...next, phase: "expired", phaseBeforeOffline: "expired", progress: null };
        case "quota.limited":
          return {
            ...next,
            phase: "limited",
            phaseBeforeOffline: "limited",
            errorCode: text(data.code, "quota_exceeded"),
            errorMessage: text(data.message, "Sandbox usage limit reached."),
            progress: null,
          };
        case "error": {
          const code = text(data.code, "turn_error");
          return {
            ...next,
            phase: data.fatal === true ? "fatal" : "error",
            errorCode: code,
            errorMessage: publicError(code, text(data.message, "The turn could not continue.")),
            progress: null,
          };
        }
        default:
          return next;
      }
    }
  }
}
