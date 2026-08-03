import { createServerClient } from "@supabase/ssr";
import type { JwtPayload } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";
import {
  getAdminUserIds,
  getSupabasePublicConfig,
  getSuspendedUserIds,
} from "./config";
import {
  decideRouteAccess,
  isProtectedPath,
  type AuthIdentity,
  type RouteAccessDecision,
} from "./routing";
import { AUTH_E2E_COOKIE, getE2EIdentity, isAuthE2EMode } from "./test-mode";

function identityFromClaims(claims: JwtPayload): AuthIdentity | null {
  if (typeof claims.sub !== "string" || !claims.sub) {
    return null;
  }

  return {
    id: claims.sub,
    email: typeof claims.email === "string" ? claims.email : null,
    assuranceLevel:
      claims.aal === "aal2" ? "aal2" : claims.aal === "aal1" ? "aal1" : null,
  };
}

function redirectForDecision(
  request: NextRequest,
  decision: Exclude<RouteAccessDecision, { kind: "allow" }>,
  sessionResponse: NextResponse,
): NextResponse {
  let redirectResponse: NextResponse;

  if (decision.kind === "sandbox") {
    const url = request.nextUrl.clone();
    url.pathname = "/sandbox";
    url.search = "";
    url.searchParams.set("error", decision.error);
    redirectResponse = NextResponse.redirect(url);
  } else if (decision.kind === "mfa") {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/mfa";
    url.search = "";
    url.searchParams.set(
      "next",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    );
    redirectResponse = NextResponse.redirect(url);
  } else {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set(
      "next",
      `${request.nextUrl.pathname}${request.nextUrl.search}`,
    );
    if (decision.error) {
      url.searchParams.set("error", decision.error);
    }
    redirectResponse = NextResponse.redirect(url);
  }

  sessionResponse.cookies.getAll().forEach((cookie) => {
    redirectResponse.cookies.set(cookie);
  });
  for (const header of ["cache-control", "pragma", "expires"]) {
    const value = sessionResponse.headers.get(header);
    if (value) {
      redirectResponse.headers.set(header, value);
    }
  }

  return redirectResponse;
}

function enforceAccess(
  request: NextRequest,
  identity: AuthIdentity | null,
  response: NextResponse,
): NextResponse {
  const decision = decideRouteAccess(
    request.nextUrl.pathname,
    identity,
    getAdminUserIds(),
    getSuspendedUserIds(),
  );

  if (decision.kind === "allow") {
    return response;
  }

  return redirectForDecision(request, decision, response);
}

export async function updateAuthSession(
  request: NextRequest,
): Promise<NextResponse> {
  if (isAuthE2EMode()) {
    const identity = getE2EIdentity(request.cookies.get(AUTH_E2E_COOKIE)?.value);
    return enforceAccess(request, identity, NextResponse.next({ request }));
  }

  const config = getSupabasePublicConfig();
  if (!config) {
    if (!isProtectedPath(request.nextUrl.pathname)) {
      return NextResponse.next({ request });
    }
    return enforceAccess(request, null, NextResponse.next({ request }));
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(config.url, config.publishableKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value);
        });
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
        Object.entries(headers).forEach(([name, value]) => {
          response.headers.set(name, value);
        });
      },
    },
  });

  const { data, error } = await supabase.auth.getClaims();
  const identity =
    !error && data?.claims ? identityFromClaims(data.claims) : null;

  return enforceAccess(request, identity, response);
}
