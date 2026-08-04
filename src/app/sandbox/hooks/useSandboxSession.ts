"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import {
  apiBaseUrl,
  getSandboxApiClient,
  type SandboxApi,
} from "@/lib/api/client";
import { ApiClientError, apiErrorMessage } from "@/lib/api/errors";
import {
  RealtimeClient,
  type RealtimeClientOptions,
} from "@/lib/realtime";

import {
  initialSandboxState,
  sandboxReducer,
} from "../state/sandboxReducer";

export type FundingSelection = {
  fundingMode: "owner_funded" | "byok";
  provider: "openai" | "anthropic";
};

export type RealtimeHandle = Pick<RealtimeClient, "start" | "stop">;
export type RealtimeFactory = (
  options: RealtimeClientOptions,
) => RealtimeHandle;

export type UseSandboxSessionOptions = {
  api?: SandboxApi;
  apiUrl?: string;
  realtimeFactory?: RealtimeFactory;
  autoStart?: boolean;
};

function sessionSettings(selection: FundingSelection) {
  return {
    funding_mode: selection.fundingMode,
    provider: selection.provider,
    model:
      "server-default",
    reasoning_effort: "medium" as const,
    plan_mode: false,
    show_usage: true,
    subagents_enabled: true,
    parallel_subagents_enabled: false,
  };
}

function defaultRealtimeFactory(options: RealtimeClientOptions): RealtimeHandle {
  return new RealtimeClient(options);
}

function phaseForError(error: unknown): { fatal?: boolean; limited?: boolean } {
  if (!(error instanceof ApiClientError)) return {};
  const code = error.envelope.error.code;
  return {
    fatal: code === "sandbox_failed" || code === "sandbox_not_found",
    limited: code === "rate_limited" || code === "quota_exceeded",
  };
}

export function useSandboxSession(options: UseSandboxSessionOptions = {}) {
  const api = options.api ?? getSandboxApiClient();
  const selectedApiUrl = options.apiUrl ?? apiBaseUrl();
  const realtimeFactory = options.realtimeFactory ?? defaultRealtimeFactory;
  const [state, dispatch] = useReducer(sandboxReducer, initialSandboxState);
  const realtime = useRef<RealtimeHandle | undefined>(undefined);
  const mounted = useRef(true);
  const bootstrapped = useRef(false);

  const reportError = useCallback((error: unknown) => {
    dispatch({
      type: "api.error",
      message: apiErrorMessage(error),
      ...phaseForError(error),
    });
  }, []);

  const connect = useCallback(
    (sessionId: string, afterSequence = 0) => {
      realtime.current?.stop();
      const connection = realtimeFactory({
        api,
        apiBaseUrl: selectedApiUrl,
        sessionId,
        afterSequence,
        onEvent: (event) => dispatch({ type: "event", event }),
        onConnectionState: (connectionState, attempt) =>
          dispatch({
            type: "connection",
            state: connectionState,
            attempt,
          }),
      });
      realtime.current = connection;
      connection.start();
    },
    [api, realtimeFactory, selectedApiUrl],
  );

  const createSession = useCallback(
    async (sandboxId: string) => {
      const session = await api.createSession(sandboxId, {
        settings: sessionSettings({
          fundingMode: "owner_funded",
          provider: "openai",
        }),
      });
      if (!mounted.current) return;
      dispatch({ type: "ready", sandboxId, sessionId: session.id });
      connect(session.id);
    },
    [api, connect],
  );

  const start = useCallback(async () => {
    dispatch({ type: "provision" });
    try {
      const active = (await api.listSandboxes()).items.find((sandbox) =>
        ["creating", "ready", "busy"].includes(sandbox.status),
      );
      let sandbox = active;
      if (!sandbox) {
        try {
          sandbox = await api.createSandbox({ template_id: "vite-react" });
        } catch (error) {
          if (
            !(error instanceof ApiClientError) ||
            error.envelope.error.code !== "active_sandbox_limit"
          ) {
            throw error;
          }
          sandbox = (await api.listSandboxes()).items.find((item) =>
            ["creating", "ready", "busy"].includes(item.status),
          );
          if (!sandbox) throw error;
        }
      }
      await createSession(sandbox.id);
    } catch (error) {
      if (mounted.current) reportError(error);
    }
  }, [api, createSession, reportError]);

  useEffect(() => {
    mounted.current = true;
    if (options.autoStart !== false && !bootstrapped.current) {
      bootstrapped.current = true;
      void start();
    }
    return () => {
      mounted.current = false;
      realtime.current?.stop();
    };
  }, [options.autoStart, start]);

  useEffect(() => {
    if (!state.sandboxId || !state.changed) return;
    void api
      .listFiles(state.sandboxId)
      .then((response) => {
        if (!mounted.current) return;
        dispatch({
          type: "files",
          changed: response.items.some(
            (item) => item.path === "components/Pricing.tsx",
          ),
        });
      })
      .catch(reportError);
  }, [api, reportError, state.changed, state.sandboxId]);

  useEffect(() => {
    if (!state.sessionId || state.phase !== "done") return;
    void api
      .listArtifacts(state.sessionId)
      .then((response) => {
        if (mounted.current) {
          dispatch({ type: "artifacts", artifacts: response.items });
        }
      })
      .catch(reportError);
  }, [api, reportError, state.phase, state.sessionId]);

  const submit = useCallback(
    async (
      message: string,
      selection: FundingSelection,
      providerApiKey?: string,
    ) => {
      if (!state.sessionId) return;
      const id = `user-${Date.now()}-${state.lastSequence}`;
      dispatch({ type: "user.message", id, text: message });
      try {
        await api.createTurn(state.sessionId, {
          message,
          settings: sessionSettings(selection),
          ...(selection.fundingMode === "byok"
            ? { provider_api_key: providerApiKey }
            : {}),
        });
      } catch (error) {
        reportError(error);
      }
    },
    [api, reportError, state.lastSequence, state.sessionId],
  );

  const resolveApproval = useCallback(
    async (approved: boolean) => {
      if (!state.sessionId || !state.approval) return;
      try {
        await api.resolveApproval(state.sessionId, state.approval.id, {
          approved,
          reason: approved ? "User approved fake validation." : "User denied.",
        });
      } catch (error) {
        reportError(error);
      }
    },
    [api, reportError, state.approval, state.sessionId],
  );

  const cancel = useCallback(async () => {
    if (!state.sessionId) return;
    try {
      await api.cancelTurn(state.sessionId);
    } catch (error) {
      reportError(error);
    }
  }, [api, reportError, state.sessionId]);

  const compact = useCallback(async () => {
    if (!state.sessionId) return;
    try {
      await api.compactSession(state.sessionId);
    } catch (error) {
      reportError(error);
    }
  }, [api, reportError, state.sessionId]);

  const reset = useCallback(async () => {
    if (!state.sandboxId) return start();
    realtime.current?.stop();
    dispatch({ type: "provision" });
    try {
      const sandbox = await api.resetSandbox(state.sandboxId);
      await createSession(sandbox.id);
    } catch (error) {
      reportError(error);
    }
  }, [api, createSession, reportError, start, state.sandboxId]);

  const deleteSandbox = useCallback(async () => {
    if (!state.sandboxId) return;
    realtime.current?.stop();
    try {
      await api.deleteSandbox(state.sandboxId);
      dispatch({ type: "reset" });
    } catch (error) {
      reportError(error);
    }
  }, [api, reportError, state.sandboxId]);

  return {
    state,
    start,
    submit,
    resolveApproval,
    cancel,
    compact,
    reset,
    deleteSandbox,
  };
}
