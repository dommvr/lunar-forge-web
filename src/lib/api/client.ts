"use client";

import { getAuthenticatedApiToken } from "@/lib/auth/api-token";

import { LunarForgeApiClient } from "./generated/client";

export type SandboxApi = Pick<
  LunarForgeApiClient,
  | "createSandbox"
  | "listSandboxes"
  | "getSandbox"
  | "resetSandbox"
  | "deleteSandbox"
  | "downloadSandbox"
  | "createSession"
  | "createTurn"
  | "resolveApproval"
  | "cancelTurn"
  | "compactSession"
  | "replayEvents"
  | "listFiles"
  | "getFile"
  | "listArtifacts"
  | "downloadArtifact"
  | "createRealtimeTicket"
>;

export function apiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_LUNAR_FORGE_API_URL ?? "http://127.0.0.1:8080"
  ).replace(/\/$/, "");
}

async function accessToken(): Promise<string> {
  if (
    process.env.NEXT_PUBLIC_LUNAR_FORGE_API_E2E_MODE === "playwright" &&
    process.env.NODE_ENV !== "production"
  ) {
    return "e2e-user";
  }
  return getAuthenticatedApiToken();
}

let browserClient: LunarForgeApiClient | undefined;

export function getSandboxApiClient(): LunarForgeApiClient {
  browserClient ??= new LunarForgeApiClient({
    baseUrl: apiBaseUrl(),
    getAccessToken: accessToken,
  });
  return browserClient;
}
