"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { createBrowserSupabaseClient } from "@/lib/auth/client";
import { AuthConfigurationError } from "@/lib/auth/config";

import styles from "./auth.module.css";

export function ResetRequestForm() {
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();

    try {
      const supabase = createBrowserSupabaseClient();
      const redirectTo = new URL("/auth/callback", window.location.origin);
      redirectTo.searchParams.set("next", "/auth/update-password");
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(
        email,
        { redirectTo: redirectTo.toString() },
      );

      if (resetError) {
        setError("A reset link could not be requested. Try again later.");
        return;
      }

      setSent(true);
    } catch (caught) {
      setError(
        caught instanceof AuthConfigurationError
          ? "Authentication is not configured for this deployment."
          : "A reset link could not be requested. Try again later.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className={styles.success} role="status">
        If an account can be reset, a password link is on its way. Check your
        inbox and spam folder.
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      {error ? (
        <div className={styles.error} role="alert">
          {error}
        </div>
      ) : null}
      <label className={styles.field}>
        <span>Account email</span>
        <input
          name="email"
          type="email"
          autoComplete="email"
          required
          autoFocus
        />
      </label>
      <Button type="submit" size="block" loading={loading} disabled={loading}>
        Send reset link
      </Button>
    </form>
  );
}
