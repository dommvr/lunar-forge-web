import type { Metadata } from "next";

import styles from "./admin.module.css";

export const metadata: Metadata = {
  title: "Administration",
  description: "Protected LunarForge administration shell.",
};

const SECTIONS = [
  {
    id: "users",
    title: "Users and invitations",
    description: "Invite, suspend, and restore controls will appear here.",
  },
  {
    id: "sandboxes",
    title: "Active sandboxes",
    description: "Runtime status and force-termination controls are not connected yet.",
  },
  {
    id: "usage",
    title: "Usage and limits",
    description: "Per-user quotas and the owner-funded daily cap will be backed by the API.",
  },
  {
    id: "settings",
    title: "Operational settings",
    description: "Kill switches and funding controls arrive with server-side persistence.",
  },
];

export default function AdminPage() {
  return (
    <>
      <div className={styles.heading}>
        <div>
          <div className={styles.eyebrow}>Private control plane</div>
          <h1>Administration</h1>
          <p>
            Authentication and MFA enforcement are active. Management data is
            intentionally deferred until the FastAPI phase.
          </p>
        </div>
        <span className={styles.mfaBadge}>MFA verified</span>
      </div>

      <div className={styles.notice} role="status">
        Shell only — no user, runtime, usage, or administrative records are
        loaded by this frontend.
      </div>

      <div className={styles.grid}>
        {SECTIONS.map((section) => (
          <section key={section.id} id={section.id} className={styles.card}>
            <div className={styles.cardTop}>
              <h2>{section.title}</h2>
              <span>Not connected</span>
            </div>
            <p>{section.description}</p>
          </section>
        ))}
      </div>
    </>
  );
}
