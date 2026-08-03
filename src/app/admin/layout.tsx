import Link from "next/link";

import { LogoutButton } from "@/components/auth/LogoutButton";
import { requireAdmin } from "@/lib/auth/session";

import styles from "./admin.module.css";

const NAV_ITEMS = [
  { label: "Overview", href: "/admin" },
  { label: "Users", href: "/admin#users" },
  { label: "Sandboxes", href: "/admin#sandboxes" },
  { label: "Usage", href: "/admin#usage" },
  { label: "Settings", href: "/admin#settings" },
];

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const identity = await requireAdmin("/admin");

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Link href="/" className={styles.brand}>
          <span className={styles.mark} aria-hidden="true">
            L
          </span>
          <span>LunarForge</span>
          <span className={styles.section}>admin</span>
        </Link>
        <div className={styles.account}>
          <span>{identity.email ?? "Administrator"}</span>
          <LogoutButton />
        </div>
      </header>
      <div className={styles.body}>
        <aside className={styles.sidebar}>
          <nav aria-label="Administration">
            {NAV_ITEMS.map((item, index) => (
              <Link
                key={item.label}
                href={item.href}
                className={index === 0 ? styles.activeLink : styles.navLink}
                aria-current={index === 0 ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <p>Management data connects in a later backend phase.</p>
        </aside>
        <main id="main" className={styles.main}>
          {children}
        </main>
      </div>
    </div>
  );
}
