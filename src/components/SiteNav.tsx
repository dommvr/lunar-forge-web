"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { ButtonLink } from "@/components/ui/Button";

import { useSearch } from "./SearchProvider";
import styles from "./SiteNav.module.css";

const LINKS = [
  { label: "Home", href: "/" },
  { label: "Docs", href: "/docs" },
  { label: "Sandbox", href: "/sandbox" },
  { label: "Compare", href: "/compare" },
  { label: "GitHub", href: "https://github.com/lunarforge/lunarforge" },
];

function isActive(pathname: string, href: string) {
  if (href.startsWith("http")) return false;
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function SiteNav({ variant = "marketing" }: { variant?: "marketing" | "docs" }) {
  const pathname = usePathname() ?? "/";
  const [menuOpen, setMenuOpen] = useState(false);
  const search = useSearch();
  const toggleRef = useRef<HTMLButtonElement>(null);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
    toggleRef.current?.focus();
  }, []);

  /* Escape closes the mobile menu and returns focus to the toggle. */
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeMenu();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen, closeMenu]);

  /* Route changes always dismiss the menu. */
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const brand = (
    <Link href="/" className={styles.brand}>
      <span className={styles.mark} aria-hidden="true">
        L
      </span>
      <span className={styles.word}>LunarForge</span>
      {variant === "docs" ? (
        <span className={styles.sectionChip}>docs</span>
      ) : null}
    </Link>
  );

  const navLinks = LINKS.map((l) => {
    const active = isActive(pathname, l.href);
    return (
      <Link
        key={l.href}
        href={l.href}
        className={`${styles.link} ${active ? styles.linkActive : ""}`}
        aria-current={active ? "page" : undefined}
        {...(l.href.startsWith("http")
          ? { target: "_blank", rel: "noreferrer noopener" }
          : {})}
      >
        {l.label}
      </Link>
    );
  });

  const openSearch = search.open;

  return (
    <header
      className={`${styles.header} ${variant === "docs" ? styles.docs : ""}`}
    >
      <div className={styles.bar}>
        <div className={styles.left}>
          {brand}
          <nav className={styles.links} aria-label="Primary">
            {navLinks}
          </nav>
        </div>
        <div className={styles.right}>
          {variant === "docs" ? (
            <button
              type="button"
              className={styles.searchField}
              onClick={openSearch}
            >
              Search documentation
              <span className={styles.kbd}>⌘K</span>
            </button>
          ) : (
            <button
              type="button"
              className={styles.searchChip}
              onClick={openSearch}
            >
              Search docs
              <span className={styles.kbd}>⌘K</span>
            </button>
          )}
          <ButtonLink
            href="/sandbox"
            variant="primary"
            size={variant === "docs" ? "nav" : "navLg"}
          >
            Try the sandbox
          </ButtonLink>
        </div>
      </div>

      <div className={styles.mobileBar}>
        {brand}
        <div className={styles.mobileActions}>
          {variant === "docs" ? (
            <button
              type="button"
              className={styles.iconButton}
              onClick={openSearch}
              aria-label="Search documentation"
            >
              ⌕
            </button>
          ) : (
            <ButtonLink href="/sandbox" variant="primary" size="sm">
              Sandbox
            </ButtonLink>
          )}
          <button
            ref={toggleRef}
            type="button"
            className={styles.iconButton}
            aria-expanded={menuOpen}
            aria-controls="site-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? (
              "×"
            ) : (
              <>
                <span className={styles.burgerLine} />
                <span className={styles.burgerLine} />
              </>
            )}
          </button>
        </div>
      </div>

      {menuOpen ? (
        <nav id="site-menu" className={styles.menu} aria-label="Mobile">
          {LINKS.map((l) => {
            const active = isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`${styles.menuLink} ${active ? styles.menuLinkActive : ""}`}
                aria-current={active ? "page" : undefined}
                onClick={() => setMenuOpen(false)}
                {...(l.href.startsWith("http")
                  ? { target: "_blank", rel: "noreferrer noopener" }
                  : {})}
              >
                {l.label}
              </Link>
            );
          })}
          <Link href="/sandbox" className={styles.menuCta}>
            Try the sandbox
          </Link>
        </nav>
      ) : null}
    </header>
  );
}
