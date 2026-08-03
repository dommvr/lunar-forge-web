import { NextResponse, type NextRequest } from "next/server";

import { createServerSupabaseClient } from "@/lib/auth/server";
import { AUTH_E2E_COOKIE, isAuthE2EMode } from "@/lib/auth/test-mode";

export async function POST(request: NextRequest) {
  if (isAuthE2EMode()) {
    const response = NextResponse.redirect(new URL("/login", request.url), 303);
    response.cookies.delete(AUTH_E2E_COOKIE);
    return response;
  }

  try {
    const supabase = await createServerSupabaseClient();
    await supabase.auth.signOut({ scope: "local" });
  } catch {
    // A missing or expired session is already signed out from the app's view.
  }

  return NextResponse.redirect(new URL("/login", request.url), 303);
}
