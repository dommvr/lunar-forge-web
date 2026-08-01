"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import styles from "./CodeBlock.module.css";

type Density = "default" | "dense" | "roomy";

type Props = {
  /** Single label shown on the left of the header bar. */
  label?: string;
  /** Language tabs; the first entry is active. Mutually exclusive with `label`. */
  tabs?: string[];
  /** Plain text put on the clipboard by the Copy button. */
  copyText: string;
  density?: Density;
  children: React.ReactNode;
};

export function CodeBlock({
  label,
  tabs,
  copyText,
  density = "default",
  children,
}: Props) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1600);
    } catch {
      /* Clipboard permission denied — leave the label untouched. */
    }
  }, [copyText]);

  const copyButton = (
    <button
      type="button"
      onClick={onCopy}
      className={`${styles.copy} ${copied ? styles.copyDone : ""}`}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );

  return (
    <div
      className={`${styles.wrap} ${density !== "default" ? styles[density] : ""}`}
    >
      {tabs ? (
        <div className={styles.tabs}>
          {tabs.map((t, i) => (
            <span
              key={t}
              className={`${styles.tab} ${i === 0 ? styles.tabActive : ""}`}
            >
              {t}
            </span>
          ))}
          <span style={{ marginLeft: "auto" }}>{copyButton}</span>
        </div>
      ) : (
        <div className={styles.head}>
          <span>{label}</span>
          {copyButton}
        </div>
      )}
      <pre className={styles.pre}>{children}</pre>
    </div>
  );
}
