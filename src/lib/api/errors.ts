import type { ErrorEnvelope } from "./generated/client";

export class ApiClientError extends Error {
  constructor(
    public readonly status: number,
    public readonly envelope: ErrorEnvelope,
  ) {
    super(envelope.error.message);
    this.name = "ApiClientError";
  }
}

export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError) return error.envelope.error.message;
  if (error instanceof Error && error.message) return error.message.slice(0, 500);
  return "The sandbox service could not complete the request.";
}
