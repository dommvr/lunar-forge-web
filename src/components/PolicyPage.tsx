import type { ReactNode } from "react";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";

import styles from "./PolicyPage.module.css";

export function PolicyPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <>
      <SiteNav />
      <main id="main" className={styles.main}>
        <article className={styles.article}>
          <div className={styles.review}>Owner review required before launch</div>
          <h1>{title}</h1>
          <p className={styles.updated}>Placeholder last updated {updated}</p>
          <div className={styles.content}>{children}</div>
        </article>
      </main>
      <SiteFooter variant="compact" note="Policy drafts require owner review." />
    </>
  );
}
