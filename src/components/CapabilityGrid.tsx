"use client";

import { useState } from "react";

import type { Capability } from "@/lib/landing";

import styles from "@/app/page.module.css";

const MOBILE_VISIBLE = 5;

/**
 * All ten capabilities on tablet and up. On mobile the mockup shows five with a
 * "+ 5 more" affordance, so the rest collapse behind a disclosure there only.
 */
export function CapabilityGrid({ items }: { items: Capability[] }) {
  const [expanded, setExpanded] = useState(false);
  const hidden = items.length - MOBILE_VISIBLE;

  return (
    <>
      <div className={styles.capGrid} data-collapsed={!expanded}>
        {items.map((c, i) => (
          <article
            key={c.n}
            className={`${styles.card} ${i >= MOBILE_VISIBLE ? styles.overflowCard : ""}`}
          >
            <div className={styles.cardIndex}>{c.n}</div>
            <h3 className={styles.cardTitle}>{c.title}</h3>
            <p className={styles.cardBody}>{c.description}</p>
          </article>
        ))}
      </div>
      {hidden > 0 && !expanded ? (
        <button
          type="button"
          className={styles.more}
          onClick={() => setExpanded(true)}
        >
          + {hidden} more capabilities
        </button>
      ) : null}
    </>
  );
}
