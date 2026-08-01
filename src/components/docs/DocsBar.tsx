"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useSearch } from "@/components/SearchProvider";
import { docsNav, type TocEntry } from "@/lib/docs";

import styles from "@/app/docs/docs.module.css";

type Props = {
  /** Breadcrumb section, e.g. "Execution". */
  section?: string;
  /** Current page label. */
  page: string;
  /** When present, the bar also offers the collapsed "On this page" list. */
  toc?: TocEntry[];
};

/**
 * Mobile/laptop bar under the navbar. The breadcrumb opens the docs drawer;
 * below 1280 the table of contents collapses into a disclosure here, closed by
 * default. Escape closes the drawer and returns focus to its trigger.
 */
export function DocsBar({ section, page, toc }: Props) {
  const pathname = usePathname() ?? "";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tocOpen, setTocOpen] = useState(false);
  const search = useSearch();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
    triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDrawer();
    };
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [drawerOpen, closeDrawer]);

  return (
    <>
      <div className={styles.mobileBar}>
        <button
          ref={triggerRef}
          type="button"
          className={styles.mobileCrumb}
          onClick={() => setDrawerOpen(true)}
          aria-expanded={drawerOpen}
          aria-label="Open documentation navigation"
        >
          {section ? (
            <>
              <span className={styles.mobileCrumbSection}>{section}</span>
              <span className={styles.breadcrumbSep}>/</span>
            </>
          ) : null}
          {page}
          <span className={styles.caret} aria-hidden="true">
            ▾
          </span>
        </button>

        {toc ? (
          <button
            type="button"
            className={styles.tocToggle}
            onClick={() => setTocOpen((v) => !v)}
            aria-expanded={tocOpen}
            aria-controls="mobile-toc"
          >
            On this page
            <span className={styles.caret} aria-hidden="true">
              {tocOpen ? "▴" : "▾"}
            </span>
          </button>
        ) : null}
      </div>

      {toc ? (
        <div
          id="mobile-toc"
          className={`${styles.mobileToc} ${tocOpen ? styles.mobileTocOpen : ""}`}
        >
          {toc.map((t) => (
            <a
              key={t.id}
              href={`#${t.id}`}
              className={`${styles.tocLink} ${t.level ? styles.tocSub : ""}`}
              onClick={() => setTocOpen(false)}
            >
              {t.title}
            </a>
          ))}
        </div>
      ) : null}

      {drawerOpen ? (
        <div
          className={styles.drawer}
          role="dialog"
          aria-modal="true"
          aria-label="Documentation navigation"
        >
          <div className={styles.drawerHead}>
            <span className={styles.drawerTitle}>Documentation</span>
            <button
              ref={closeRef}
              type="button"
              className={styles.drawerClose}
              onClick={closeDrawer}
              aria-label="Close navigation"
            >
              ×
            </button>
          </div>
          <div className={styles.drawerBody}>
            <button
              type="button"
              className={styles.drawerSearch}
              onClick={() => {
                setDrawerOpen(false);
                search.open();
              }}
            >
              Search documentation
              <span className={styles.drawerSearchGlyph} aria-hidden="true">
                ⌕
              </span>
            </button>

            {docsNav.map((group) => (
              <div key={group.title}>
                <div className={styles.drawerGroupTitle}>{group.title}</div>
                {group.items.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`${styles.drawerItem} ${active ? styles.drawerItemActive : ""}`}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </>
  );
}
