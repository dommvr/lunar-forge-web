import type { SupabaseClient } from "@supabase/supabase-js";
import { createBrowserSupabaseClient } from "./client";

export class MissingApiTokenError extends Error {
  constructor() {
    super("An authenticated Supabase session is required.");
    this.name = "MissingApiTokenError";
  }
}

export async function getAuthenticatedApiToken(
  client: SupabaseClient = createBrowserSupabaseClient(),
): Promise<string> {
  const { data: claimsData, error: claimsError } = await client.auth.getClaims();
  if (claimsError || !claimsData?.claims?.sub) {
    throw new MissingApiTokenError();
  }

  const { data: sessionData, error: sessionError } =
    await client.auth.getSession();
  const accessToken = sessionData.session?.access_token;

  if (sessionError || !accessToken) {
    throw new MissingApiTokenError();
  }

  return accessToken;
}

export async function getAuthenticatedApiHeaders(
  client?: SupabaseClient,
): Promise<HeadersInit> {
  const token = await getAuthenticatedApiToken(client);
  return { Authorization: `Bearer ${token}` };
}
