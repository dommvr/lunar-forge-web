export type SupabasePublicConfig = {
  url: string;
  publishableKey: string;
};

export class AuthConfigurationError extends Error {
  constructor() {
    super(
      "Supabase Auth is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.",
    );
    this.name = "AuthConfigurationError";
  }
}

export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const publishableKey =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!url || !publishableKey) {
    return null;
  }

  return { url, publishableKey };
}

export function requireSupabasePublicConfig(): SupabasePublicConfig {
  const config = getSupabasePublicConfig();
  if (!config) {
    throw new AuthConfigurationError();
  }

  return config;
}

function parseIdList(value: string | undefined): ReadonlySet<string> {
  return new Set(
    (value ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
}

export function getAdminUserIds(): ReadonlySet<string> {
  return parseIdList(process.env.LUNAR_FORGE_ADMIN_USER_IDS);
}

export function getSuspendedUserIds(): ReadonlySet<string> {
  return parseIdList(process.env.LUNAR_FORGE_SUSPENDED_USER_IDS);
}
