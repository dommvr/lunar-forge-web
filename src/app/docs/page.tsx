import type { Metadata } from "next";
import Link from "next/link";

import { DocsBar } from "@/components/docs/DocsBar";
import { docsOverview } from "@/lib/docs";

import styles from "./docs.module.css";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Install the agent, point it at a project, and understand exactly what it is allowed to do.",
};

export default function DocsOverviewPage() {
  return (
    <>
      <DocsBar page="Documentation" />
      <article className={styles.overview}>
        <div className={styles.kicker}>Documentation</div>
        <h1 className={styles.h1}>LunarForge documentation</h1>
        <p className={styles.intro}>
          Install the core agent, point it at a project, and understand exactly
          what it is allowed to do. Navigation and search below are generated
          from the MDX content in this portal.
        </p>

        <div className={styles.startCards}>
          <Link
            href="/docs/quick-start"
            className={`${styles.startCard} ${styles.startCardFeatured}`}
          >
            <span className={styles.startCardLabel}>START HERE</span>
            <span className={styles.startCardTitle}>Quick start</span>
            <span className={styles.startCardBody}>
              Inspect in plan mode, then opt into guarded local or Docker work.
            </span>
          </Link>
          <Link href="/docs/security-model" className={styles.startCard}>
            <span className={styles.startCardLabel}>READ NEXT</span>
            <span className={styles.startCardTitle}>Security model</span>
            <span className={styles.startCardBody}>
              What local mode does and does not isolate, and when to require
              Docker.
            </span>
          </Link>
        </div>

        <div className={styles.sections}>
          {docsOverview.map((section) => (
            <section key={section.title}>
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle}>{section.title}</h2>
                <span className={styles.rule} aria-hidden="true" />
              </div>
              <div className={styles.tileGrid}>
                {section.items.map((item) => (
                  <Link
                    key={item.title}
                    href={item.href}
                    className={styles.tile}
                  >
                    <span className={styles.tileTitle}>{item.title}</span>
                    <span className={styles.tileBody}>{item.description}</span>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </article>
    </>
  );
}
