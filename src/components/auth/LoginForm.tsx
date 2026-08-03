"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { createBrowserSupabaseClient } from "@/lib/auth/client";
import { AuthConfigurationError } from "@/lib/auth/config";
import { safeNextPath } from "@/lib/auth/routing";

import styles from "./auth.module.css";

export function LoginForm({
  nextPath,
  initialError,
}: {
  nextPath: string;
  initialError?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState(initialError ?? "");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");

    try {
      const supabase = createBrowserSupabaseClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        setError("Email or password was not accepted.");
        return;
      }

      router.replace(safeNextPath(nextPath));
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof AuthConfigurationError
          ? "Authentication is not configured for this deployment."
          : "Sign in could not be completed. Try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      {error ? (
        <div className={styles.error} role="alert">
          {error}
        </div>
      ) : null}

      <label className={styles.field}>
        <span>Email</span>
        <input
          name="email"
          type="email"
          autoComplete="email"
          required
          autoFocus
        />
      </label>

      <label className={styles.field}>
        <span>Password</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
      </label>

      <div className={styles.formMeta}>
        <span>Access is invite-only.</span>
        <Link href="/login/reset">Forgot password?</Link>
      </div>

      <Button type="submit" size="block" loading={loading} disabled={loading}>
        Sign in
      </Button>
    </form>
  );
}
