import type { ReactNode } from "react";

import styles from "./Callout.module.css";

export type CalloutKind = "note" | "tip" | "warning" | "danger";

const LABEL: Record<CalloutKind, string> = {
  note: "NOTE",
  tip: "TIP",
  warning: "WARNING",
  danger: "DANGER",
};

export function Callout({
  kind,
  label,
  compact = false,
  children,
}: {
  kind: CalloutKind;
  /** Override the default label (the mobile article shortens WARNING to WARN). */
  label?: string;
  compact?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={`${styles.callout} ${styles[kind]} ${compact ? styles.compact : ""}`}
    >
      <div className={styles.kind}>{label ?? LABEL[kind]}</div>
      <div className={styles.body}>{children}</div>
    </div>
  );
}
