"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { createBrowserSupabaseClient } from "@/lib/auth/client";
import { safeNextPath } from "@/lib/auth/routing";

import styles from "./auth.module.css";

type MfaState =
  | { kind: "loading" }
  | { kind: "challenge"; factorId: string }
  | { kind: "enroll"; factorId: string; qrCode: string; secret: string }
  | { kind: "error"; message: string };

export function MfaForm({ nextPath = "/admin" }: { nextPath?: string }) {
  const router = useRouter();
  const [state, setState] = useState<MfaState>({ kind: "loading" });
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    let active = true;

    async function prepare() {
      try {
        const supabase = createBrowserSupabaseClient();
        const { data: assurance } =
          await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
        if (assurance?.currentLevel === "aal2") {
          router.replace(safeNextPath(nextPath, "/admin"));
          router.refresh();
          return;
        }

        const { data: factors, error: factorsError } =
          await supabase.auth.mfa.listFactors();
        if (factorsError) {
          throw factorsError;
        }

        const verified = factors.totp.find(
          (factor) => factor.status === "verified",
        );
        if (verified) {
          if (active) {
            setState({ kind: "challenge", factorId: verified.id });
          }
          return;
        }

        const { data: enrollment, error: enrollmentError } =
          await supabase.auth.mfa.enroll({
            factorType: "totp",
            friendlyName: "LunarForge admin",
          });
        if (enrollmentError) {
          throw enrollmentError;
        }

        if (active) {
          setState({
            kind: "enroll",
            factorId: enrollment.id,
            qrCode: enrollment.totp.qr_code,
            secret: enrollment.totp.secret,
          });
        }
      } catch {
        if (active) {
          setState({
            kind: "error",
            message: "Multi-factor authentication could not be prepared.",
          });
        }
      }
    }

    void prepare();
    return () => {
      active = false;
    };
  }, [nextPath, router]);

  async function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.kind !== "challenge" && state.kind !== "enroll") {
      return;
    }

    setSubmitError("");
    setSubmitting(true);
    try {
      const supabase = createBrowserSupabaseClient();
      const { error } = await supabase.auth.mfa.challengeAndVerify({
        factorId: state.factorId,
        code: code.replace(/\s/g, ""),
      });
      if (error) {
        setSubmitError("That verification code was not accepted.");
        return;
      }

      router.replace(safeNextPath(nextPath, "/admin"));
      router.refresh();
    } catch {
      setSubmitError("Verification could not be completed. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (state.kind === "loading") {
    return <div className={styles.status}>Preparing your authenticator…</div>;
  }

  if (state.kind === "error") {
    return (
      <div className={styles.error} role="alert">
        {state.message}
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={verify}>
      {state.kind === "enroll" ? (
        <div className={styles.enrollment}>
          <p>
            Scan this code with your authenticator app, then enter the six-digit
            code it generates.
          </p>
          <div className={styles.qrFrame}>
            <Image
              src={state.qrCode}
              alt="Authenticator enrollment QR code"
              width={184}
              height={184}
              unoptimized
            />
          </div>
          <details className={styles.secret}>
            <summary>Enter a setup key instead</summary>
            <code>{state.secret}</code>
          </details>
        </div>
      ) : (
        <p className={styles.hint}>
          Enter the current six-digit code from your authenticator app.
        </p>
      )}

      {submitError ? (
        <div className={styles.error} role="alert">
          {submitError}
        </div>
      ) : null}

      <label className={styles.field}>
        <span>Verification code</span>
        <input
          name="code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9 ]{6,11}"
          required
          autoFocus={state.kind === "challenge"}
        />
      </label>

      <Button
        type="submit"
        size="block"
        loading={submitting}
        disabled={submitting}
      >
        Verify and continue
      </Button>
    </form>
  );
}
