import Link from "next/link";
import type { ReactNode } from "react";

import styles from "./auth.module.css";

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main id="main" className={styles.page}>
      <div className={styles.glow} aria-hidden="true" />
      <Link href="/" className={styles.brand} aria-label="LunarForge home">
        <span className={styles.mark} aria-hidden="true">
          L
        </span>
        <span>LunarForge</span>
      </Link>

      <section className={styles.card}>
        <div className={styles.eyebrow}>{eyebrow}</div>
        <h1>{title}</h1>
        <p className={styles.intro}>{description}</p>
        {children}
      </section>

      <nav className={styles.legal} aria-label="Policy links">
        <Link href="/privacy">Privacy</Link>
        <Link href="/security">Security</Link>
        <Link href="/terms">Terms</Link>
      </nav>
    </main>
  );
}
