import Link from "next/link";

import { footerColumns, RELEASE, RELEASE_SHORT } from "@/lib/landing";

import styles from "./SiteFooter.module.css";

const COMPACT_LINKS = [
  { label: "Home", href: "/" },
  { label: "Docs", href: "/docs" },
  { label: "Sandbox", href: "/sandbox" },
  { label: "GitHub", href: "https://github.com/lunarforge/lunarforge" },
];

export function SiteFooter({
  variant = "full",
  note,
}: {
  variant?: "full" | "compact";
  note?: string;
}) {
  if (variant === "compact") {
    return (
      <footer className={`${styles.footer} ${styles.compact}`}>
        <div className={styles.compactMeta}>
          <div className={styles.release}>{RELEASE_SHORT}</div>
          {note ? <div className={styles.compactNote}>{note}</div> : null}
        </div>
        <nav className={styles.inlineLinks} aria-label="Footer">
          {COMPACT_LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={styles.link}>
              {l.label}
            </Link>
          ))}
        </nav>
      </footer>
    );
  }

  return (
    <footer className={styles.footer}>
      <div className={styles.about}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden="true" />
          <span className={styles.name}>LunarForge</span>
        </div>
        <p className={styles.blurb}>
          A Python coding agent that inspects projects, plans and edits safely,
          runs approved commands locally or in Docker, and emits a structured
          event stream for any interface.
        </p>
        <div className={styles.release}>{RELEASE}</div>
      </div>
      <nav className={styles.columns} aria-label="Footer">
        {footerColumns.map((col) => (
          <div key={col.title} className={styles.column}>
            <div className={styles.columnTitle}>{col.title}</div>
            {col.items.map((item) => (
              <Link key={item.label} href={item.href} className={styles.link}>
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
    </footer>
  );
}
