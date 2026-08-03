"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { createBrowserSupabaseClient } from "@/lib/auth/client";
import { safeNextPath } from "@/lib/auth/routing";

import styles from "./auth.module.css";

export function PasswordSetupForm({
  nextPath = "/sandbox",
  submitLabel = "Set password",
}: {
  nextPath?: string;
  submitLabel?: string;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("confirmation") ?? "");

    if (password.length < 12) {
      setError("Use at least 12 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const supabase = createBrowserSupabaseClient();
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) {
        setError("The password could not be updated. Request a new link.");
        return;
      }

      router.replace(safeNextPath(nextPath));
      router.refresh();
    } catch {
      setError("The password could not be updated. Request a new link.");
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
        <span>New password</span>
        <input
          name="password"
          type="password"
          minLength={12}
          autoComplete="new-password"
          required
          autoFocus
        />
      </label>
      <label className={styles.field}>
        <span>Confirm password</span>
        <input
          name="confirmation"
          type="password"
          minLength={12}
          autoComplete="new-password"
          required
        />
      </label>
      <p className={styles.hint}>Use at least 12 characters.</p>
      <Button type="submit" size="block" loading={loading} disabled={loading}>
        {submitLabel}
      </Button>
    </form>
  );
}
