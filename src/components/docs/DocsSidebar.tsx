"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { docsNav } from "@/lib/docs";

import styles from "@/app/docs/docs.module.css";

/**
 * Independent scroll container. Groups stay expanded on desktop; the current
 * item is highlighted and scrolled into the sidebar viewport on navigation.
 */
export function DocsSidebar() {
  const pathname = usePathname() ?? "";
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    ref.current
      ?.querySelector<HTMLElement>('[aria-current="page"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [pathname]);

  return (
    <nav ref={ref} className={styles.sidebar} aria-label="Documentation">
      {docsNav.map((group) => (
        <div key={group.title} className={styles.navGroup}>
          <div className={styles.navGroupTitle}>{group.title}</div>
          {group.items.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navItem} ${active ? styles.navItemActive : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
