"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";

import {
  apiBaseUrl,
  getSandboxApiClient,
  type SandboxApi,
} from "@/lib/api/client";
import { ApiClientError, apiErrorMessage } from "@/lib/api/errors";
import type { DownloadResponse, SandboxResponse } from "@/lib/api/generated/client";
import { RealtimeClient, type RealtimeClientOptions } from "@/lib/realtime";

import { initialSandboxState, sandboxReducer } from "../state/sandboxReducer";

export type FundingSelection = {
  fundingMode: "owner_funded" | "byok";
  provider: "openai" | "anthropic";
};

export type RealtimeHandle = Pick<RealtimeClient, "start" | "stop">;
export type RealtimeFactory = (options: RealtimeClientOptions) => RealtimeHandle;

export type UseSandboxSessionOptions = {
  api?: SandboxApi;
  apiUrl?: string;
  realtimeFactory?: RealtimeFactory;
  autoStart?: boolean;
};

function sessionSettings(selection: FundingSelection) {
  return {
    funding_mode: selection.fundingMode,
    provider: selection.fundingMode === "owner_funded" ? "openai" : selection.provider,
    model: "server-default",
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

function errorState(error: unknown): {
  code?: string;
  fatal?: boolean;
  limited?: boolean;
} {
  if (!(error instanceof ApiClientError)) return {};
  const code = error.envelope.error.code;
  return {
    code,
    fatal: code === "sandbox_failed" || code === "sandbox_not_found",
    limited: [
      "rate_limit_exceeded",
      "quota_exceeded",
      "owner_funded_turn_limit",
      "owner_funded_user_cost_limit",
      "owner_funded_global_cost_limit",
      "daily_turn_limit",
      "daily_user_cost_limit",
      "daily_global_cost_limit",
      "owner_funded_disabled",
      "global_kill_switch_enabled",
      "sandbox_kill_switch",
    ].includes(code),
  };
}

function saveDownload(download: DownloadResponse): void {
  const url = URL.createObjectURL(download.blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = download.filename;
  anchor.rel = "noopener";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
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
      ...errorState(error),
    });
  }, []);

  const recordSandbox = useCallback((sandbox: SandboxResponse) => {
    dispatch({ type: "activity", expiresAt: sandbox.expires_at });
  }, []);

  const refreshSandbox = useCallback(
    async (sandboxId: string) => {
      const sandbox = await api.getSandbox(sandboxId);
      if (mounted.current) recordSandbox(sandbox);
      return sandbox;
    },
    [api, recordSandbox],
  );

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
          dispatch({ type: "connection", state: connectionState, attempt }),
      });
      realtime.current = connection;
      connection.start();
    },
    [api, realtimeFactory, selectedApiUrl],
  );

  const createSession = useCallback(
    async (sandbox: SandboxResponse) => {
      const session = await api.createSession(sandbox.id, {
        settings: sessionSettings({ fundingMode: "owner_funded", provider: "openai" }),
      });
      if (!mounted.current) return;
      dispatch({
        type: "ready",
        sandboxId: sandbox.id,
        sessionId: session.id,
        runtimeProvider: sandbox.runtime_provider,
        expiresAt: sandbox.expires_at,
      });
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
      await createSession(sandbox);
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
    if (!state.expiresAt || ["idle", "expired"].includes(state.phase)) return;
    const delay = new Date(state.expiresAt).getTime() - Date.now();
    if (delay <= 0) {
      dispatch({ type: "expired" });
      return;
    }
    const timer = window.setTimeout(
      () => dispatch({ type: "expired" }),
      Math.min(delay, 2_147_000_000),
    );
    return () => window.clearTimeout(timer);
  }, [state.expiresAt, state.phase]);

  useEffect(() => {
    if (!state.sandboxId) return;
    void api
      .listFiles(state.sandboxId)
      .then((response) => {
        if (mounted.current) dispatch({ type: "files", files: response });
      })
      .catch(reportError);
  }, [api, reportError, state.fileRevision, state.phase, state.sandboxId]);

  useEffect(() => {
    if (!state.sessionId || !["done", "cancelled"].includes(state.phase)) return;
    void api
      .listArtifacts(state.sessionId)
      .then((response) => {
        if (mounted.current) dispatch({ type: "artifacts", artifacts: response.items });
      })
      .catch(reportError);
  }, [api, reportError, state.phase, state.sessionId]);

  const submit = useCallback(
    async (message: string, selection: FundingSelection, providerApiKey?: string) => {
      if (!state.sessionId || !state.sandboxId) return;
      if (selection.fundingMode === "byok" && (!providerApiKey || providerApiKey.length < 8)) {
        dispatch({
          type: "api.error",
          code: "provider_authentication_failed",
          message: "Enter a valid provider credential before starting a BYOK turn.",
        });
        return;
      }
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
        await refreshSandbox(state.sandboxId);
      } catch (error) {
        reportError(error);
      }
    },
    [api, refreshSandbox, reportError, state.lastSequence, state.sandboxId, state.sessionId],
  );

  const resolveApproval = useCallback(
    async (approved: boolean) => {
      if (!state.sessionId || !state.sandboxId || !state.approval) return;
      try {
        await api.resolveApproval(state.sessionId, state.approval.id, {
          approved,
          reason: approved ? "User approved the requested action." : "User denied the action.",
        });
        await refreshSandbox(state.sandboxId);
      } catch (error) {
        reportError(error);
      }
    },
    [api, refreshSandbox, reportError, state.approval, state.sandboxId, state.sessionId],
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
      const response = await api.compactSession(state.sessionId);
      dispatch({
        type: "compaction.result",
        compacted: response.compacted,
        summary: response.summary,
      });
    } catch (error) {
      reportError(error);
    }
  }, [api, reportError, state.sessionId]);

  const openFile = useCallback(
    async (path: string) => {
      if (!state.sandboxId) return;
      try {
        const file = await api.getFile(state.sandboxId, path);
        dispatch({ type: "file.content", file });
        await refreshSandbox(state.sandboxId);
      } catch (error) {
        reportError(error);
      }
    },
    [api, refreshSandbox, reportError, state.sandboxId],
  );

  const downloadProject = useCallback(async () => {
    if (!state.sandboxId) return;
    try {
      saveDownload(await api.downloadSandbox(state.sandboxId));
      await refreshSandbox(state.sandboxId);
    } catch (error) {
      reportError(error);
    }
  }, [api, refreshSandbox, reportError, state.sandboxId]);

  const downloadArtifact = useCallback(
    async (artifactId: string) => {
      if (!state.sandboxId) return;
      try {
        const download = await api.downloadArtifact(artifactId);
        const artifact = state.artifacts.find((item) => item.id === artifactId);
        saveDownload({
          ...download,
          filename:
            download.filename === "artifact.bin" && artifact
              ? artifact.name
              : download.filename,
        });
        await refreshSandbox(state.sandboxId);
      } catch (error) {
        reportError(error);
      }
    },
    [api, refreshSandbox, reportError, state.artifacts, state.sandboxId],
  );

  const reset = useCallback(async () => {
    if (!state.sandboxId) return start();
    realtime.current?.stop();
    dispatch({ type: "provision" });
    try {
      const sandbox = await api.resetSandbox(state.sandboxId);
      await createSession(sandbox);
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
    openFile,
    downloadProject,
    downloadArtifact,
    reset,
    deleteSandbox,
  };
}
