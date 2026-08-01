"use client";

import { useEffect, useState } from "react";

import type { TocEntry } from "@/lib/docs";

import styles from "@/app/docs/docs.module.css";

/**
 * Headings are observed with IntersectionObserver; the active entry gets the
 * orange left bar.
 */
export function DocsToc({ entries }: { entries: TocEntry[] }) {
  const [active, setActive] = useState(entries[0]?.id ?? "");

  useEffect(() => {
    const targets = entries
      .map((e) => document.getElementById(e.id))
      .filter((el): el is HTMLElement => el !== null);
    if (targets.length === 0) return;

    const observer = new IntersectionObserver(
      (records) => {
        const visible = records
          .filter((r) => r.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 },
    );

    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, [entries]);

  return (
    <aside className={styles.toc} aria-label="On this page">
      <div className={styles.tocLabel}>On this page</div>
      <nav className={styles.tocList}>
        {entries.map((e) => (
          <a
            key={e.id}
            href={`#${e.id}`}
            className={[
              styles.tocLink,
              e.level ? styles.tocSub : "",
              e.id === active ? styles.tocActive : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-current={e.id === active ? "location" : undefined}
          >
            {e.title}
          </a>
        ))}
      </nav>
      <div className={styles.tocMeta}>
        <a
          className={styles.tocMetaLink}
          href="https://github.com/lunarforge/lunarforge"
        >
          Edit this page
        </a>
        <a
          className={styles.tocMetaLink}
          href="https://github.com/lunarforge/lunarforge/issues"
        >
          Report an issue
        </a>
      </div>
    </aside>
  );
}
