import type { EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

import { safeNextPath } from "@/lib/auth/routing";
import { createServerSupabaseClient } from "@/lib/auth/server";

const EMAIL_OTP_TYPES = new Set<EmailOtpType>([
  "email",
  "invite",
  "magiclink",
  "recovery",
  "signup",
  "email_change",
]);

function loginError(request: NextRequest, error: string) {
  const url = new URL("/login", request.url);
  url.searchParams.set("error", error);
  return NextResponse.redirect(url, 303);
}

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const tokenHash = request.nextUrl.searchParams.get("token_hash");
  const rawType = request.nextUrl.searchParams.get("type");
  const nextPath = safeNextPath(
    request.nextUrl.searchParams.get("next"),
    "/sandbox",
  );

  try {
    const supabase = await createServerSupabaseClient();
    let error: Error | null = null;

    if (code) {
      ({ error } = await supabase.auth.exchangeCodeForSession(code));
    } else if (
      tokenHash &&
      rawType &&
      EMAIL_OTP_TYPES.has(rawType as EmailOtpType)
    ) {
      ({ error } = await supabase.auth.verifyOtp({
        token_hash: tokenHash,
        type: rawType as EmailOtpType,
      }));
    } else {
      return loginError(request, "auth_callback_failed");
    }

    if (error) {
      return loginError(
        request,
        rawType === "invite" ? "invite_expired" : "auth_callback_failed",
      );
    }

    const destination =
      rawType === "invite"
        ? "/auth/setup-password"
        : rawType === "recovery"
          ? "/auth/update-password"
          : nextPath;
    return NextResponse.redirect(new URL(destination, request.url), 303);
  } catch {
    return loginError(request, "auth_callback_failed");
  }
}
