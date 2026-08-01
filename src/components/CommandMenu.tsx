"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  recentPages,
  searchActions,
  searchIndex,
  type SearchResult,
} from "@/lib/docs";

import styles from "./CommandMenu.module.css";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type Group = { label: string; items: SearchResult[] };

function match(r: SearchResult, q: string) {
  const needle = q.toLowerCase();
  return (
    r.title.toLowerCase().includes(needle) ||
    r.description.toLowerCase().includes(needle)
  );
}

/**
 * ⌘K / Ctrl-K anywhere. Results are grouped by kind and filtered as you type;
 * ↑↓ move, ↵ opens, ⌘↵ opens in a new tab, Escape closes and restores focus
 * to whatever opened the menu. An empty query lists recent pages.
 */
export function CommandMenu({ open, onOpenChange }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  const groups: Group[] = useMemo(() => {
    if (!query.trim()) {
      return [
        { label: "Recent", items: recentPages },
        { label: "Actions", items: searchActions },
      ];
    }
    const hits = searchIndex.filter((r) => match(r, query));
    const byKind: Group[] = [
      {
        label: `Documentation · ${hits.filter((h) => h.kind === "page").length} results`,
        items: hits.filter((h) => h.kind === "page"),
      },
      { label: "Events", items: hits.filter((h) => h.kind === "event") },
      { label: "Python API", items: hits.filter((h) => h.kind === "api") },
      {
        label: "Actions",
        items: searchActions.filter((r) => match(r, query)),
      },
    ];
    return byKind.filter((g) => g.items.length > 0);
  }, [query]);

  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  /* Global hotkey. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openerRef.current = document.activeElement as HTMLElement | null;
        onOpenChange(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onOpenChange]);

  /* Reset and lock scroll while open; restore focus on close. */
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    const opener = document.activeElement as HTMLElement | null;
    if (opener) openerRef.current = opener;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    inputRef.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      openerRef.current?.focus?.();
    };
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  /* Keep the highlighted row inside the scroll container. */
  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const go = useCallback(
    (result: SearchResult, newTab: boolean) => {
      if (newTab) {
        window.open(result.href, "_blank", "noopener,noreferrer");
        return;
      }
      onOpenChange(false);
      router.push(result.href);
    },
    [onOpenChange, router],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onOpenChange(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (flat.length ? (i + 1) % flat.length : 0));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (flat.length ? (i - 1 + flat.length) % flat.length : 0));
      return;
    }
    if (e.key === "Enter" && flat[active]) {
      e.preventDefault();
      go(flat[active], e.metaKey || e.ctrlKey);
      return;
    }
    /* Focus trap: the panel holds exactly one tab stop, so keep it. */
    if (e.key === "Tab") e.preventDefault();
  };

  if (!open) return null;

  let index = -1;

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onOpenChange(false);
      }}
    >
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-label="Search documentation"
        onKeyDown={onKeyDown}
      >
        <div className={styles.field}>
          <span className={styles.glyph} aria-hidden="true">
            ⌕
          </span>
          <input
            ref={inputRef}
            className={styles.input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documentation"
            aria-label="Search documentation"
            autoComplete="off"
            spellCheck={false}
          />
          <span className={styles.esc}>ESC</span>
        </div>

        <div className={styles.list} ref={listRef}>
          {flat.length === 0 ? (
            <div className={styles.empty}>
              No matches for “{query}”. Try an event name, or an API symbol.
            </div>
          ) : (
            groups.map((group) => (
              <div key={group.label}>
                <div className={styles.groupLabel}>{group.label}</div>
                {group.items.map((r) => {
                  index += 1;
                  const i = index;
                  return (
                    <button
                      key={`${r.kind}-${r.title}`}
                      type="button"
                      data-index={i}
                      className={`${styles.result} ${i === active ? styles.resultActive : ""}`}
                      onMouseMove={() => setActive(i)}
                      onClick={(e) => go(r, e.metaKey || e.ctrlKey)}
                    >
                      <span className={styles.kind}>{r.kind}</span>
                      <span className={styles.text}>
                        <span className={styles.title}>{r.title}</span>
                        <span className={styles.desc}>{r.description}</span>
                      </span>
                      <span className={styles.path}>{r.href}</span>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className={styles.foot}>
          <span>↑↓ navigate</span>
          <span>↵ open</span>
          <span>⌘↵ new tab</span>
          <span className={styles.footSpacer}>Search by title and body</span>
        </div>
      </div>
    </div>
  );
}
