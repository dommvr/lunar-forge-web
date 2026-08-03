import type { Metadata } from "next";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import code from "@/components/ui/CodeBlock.module.css";
import {
  breakpoints,
  calloutSamples,
  colorGroups,
  elevationRules,
  fileRows,
  interactionNotes,
  radiusScale,
  spacingScale,
  statusBadges,
  toasts,
  typeScale,
} from "@/lib/design-system";
import { sandboxStates, type StateTone } from "@/lib/sandbox";

import styles from "./ds.module.css";

export const metadata: Metadata = {
  title: "Design system",
  description:
    "Tokens, components, and interaction notes — the implementation contract for the LunarForge frontend.",
};

const SHELL = `$ python -m pip install -e .
$ lunar-forge --docker "Explain this project"
  project config: .agent/config.yaml`;

const TONE_COLOR: Record<StateTone, string> = {
  muted: "var(--text-muted)",
  warning: "var(--amber)",
  success: "var(--success)",
  accent: "var(--accent)",
  error: "var(--error)",
};

const TONE_RING: Record<StateTone, string> = {
  muted: "var(--border)",
  warning: "var(--accent-ring)",
  success: "var(--success-ring)",
  accent: "var(--accent-ring)",
  error: "var(--error-ring)",
};

export default function DesignSystemPage() {
  return (
    <>
      <SiteNav />
      <main id="main" className={styles.page}>
        <header className={styles.intro}>
          <p className={styles.kicker}>Design system</p>
          <h1 className={styles.title}>
            Tokens, components, and interaction notes
          </h1>
          <p className={styles.blurb}>
            Token names map to CSS custom properties; every value here is used
            verbatim across the implemented routes. 8-point spacing,
            restrained radii, borders instead of shadows except for overlays.
          </p>
        </header>

        {/* ---------- Tokens ---------- */}
        <section className={styles.panel} aria-label="Tokens">
          <div className={styles.block}>
            <p className={styles.panelLabel}>Color tokens</p>
            {colorGroups.map((g) => (
              <div key={g.title} className={styles.block}>
                <p className={styles.groupTitle}>{g.title}</p>
                <div className={styles.swatchGrid}>
                  {g.items.map((c) => (
                    <div key={c.name} className={styles.swatch}>
                      <div
                        className={styles.swatchChip}
                        style={{ background: c.value }}
                      />
                      <div className={styles.swatchMeta}>
                        <span className={styles.swatchName}>{c.name}</span>
                        <span className={styles.swatchValue}>{c.value}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className={styles.twoCol}>
            <div className={styles.block}>
              <p className={styles.panelLabel}>Typography scale</p>
              <div>
                {typeScale.map((t) => (
                  <div key={t.name} className={styles.typeRow}>
                    <span className={styles.typeName}>{t.name}</span>
                    <span className={styles.typeSpec}>{t.spec}</span>
                    <span
                      className={styles.typeSample}
                      style={{
                        fontFamily: t.family,
                        fontSize: t.size,
                        fontWeight: t.weight,
                        letterSpacing: t.tracking,
                      }}
                    >
                      {t.sample}
                    </span>
                  </div>
                ))}
              </div>
              <p className={styles.footnote}>
                IBM Plex Sans for interface and prose; IBM Plex Mono for code,
                event names, session metadata, and eyebrow labels. No third
                family.
              </p>
            </div>

            <div className={styles.sideStack}>
              <div className={styles.block}>
                <p className={styles.panelLabel}>Spacing · 8-point</p>
                <div className={styles.col} style={{ gap: 6 }}>
                  {spacingScale.map((s) => (
                    <div key={s.name} className={styles.spacingRow}>
                      <span className={styles.spacingName}>{s.name}</span>
                      <span className={styles.spacingValue}>{s.value}</span>
                      <span
                        className={styles.spacingBar}
                        style={{ width: s.value }}
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.block}>
                <p className={styles.panelLabel}>Radius</p>
                <div className={styles.radiusRow}>
                  {radiusScale.map((r) => (
                    <div key={r.name} className={styles.radiusItem}>
                      <span
                        className={styles.radiusBox}
                        style={{ borderRadius: r.value }}
                      />
                      <span className={styles.radiusName}>{r.name}</span>
                      <span className={styles.radiusValue}>{r.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.block}>
                <p className={styles.panelLabel}>Elevation &amp; border rules</p>
                <div>
                  {elevationRules.map((e) => (
                    <div key={e.name} className={styles.elevationRow}>
                      <span className={styles.elevationName}>{e.name}</span>
                      <span className={styles.elevationBody}>
                        {e.description}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Components ---------- */}
        <section className={styles.gallery} aria-label="Components">
          <p className={`${styles.panelLabel} ${styles.galleryLabel}`}>
            Components
          </p>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Buttons</h2>
            <div className={styles.row}>
              <Button variant="primary">Primary</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive</Button>
              <Button variant="primary" disabled>
                Disabled
              </Button>
              <Button
                variant="primary"
                style={{
                  boxShadow: "0 0 0 2px var(--bg), 0 0 0 4px var(--accent)",
                }}
              >
                Focus ring
              </Button>
              <Button variant="primary" loading style={{ opacity: 0.8 }}>
                Loading
              </Button>
              <Button variant="secondary" size="sm">
                Small
              </Button>
              <Button variant="primary" size="cta">
                Large
              </Button>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Inputs</h2>
            <div className={styles.col}>
              <div className={styles.field}>Placeholder text</div>
              <div className={`${styles.field} ${styles.fieldFocused}`}>
                Focused value
                <span className={styles.caret} />
              </div>
              <div className={`${styles.field} ${styles.fieldInvalid}`}>
                Invalid value
              </div>
              <p className={styles.fieldError}>
                Enter a valid project-local session selector.
              </p>
              <div className={`${styles.field} ${styles.fieldDisabled}`}>
                Disabled · read-only
              </div>
              <div className={`${styles.field} ${styles.fieldSearch}`}>
                Search documentation
                <span className={styles.kbd}>⌘K</span>
              </div>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Navigation &amp; tabs</h2>
            <div className={styles.navSample}>
              <span className={`${styles.navItem} ${styles.navItemActive}`}>
                Active route
              </span>
              <span className={styles.navItem}>Inactive</span>
              <span className={`${styles.navItem} ${styles.navItemHover}`}>
                Hover
              </span>
            </div>
            <div className={styles.tabStrip}>
              {["Activity", "Validation", "Artifacts", "Usage"].map((t, i) => (
                <span
                  key={t}
                  className={`${styles.tabItem} ${i === 0 ? styles.tabItemActive : ""}`}
                >
                  {t}
                </span>
              ))}
            </div>
            <div className={styles.sidebarSample}>
              <span className={styles.sidebarGroup}>Sidebar group</span>
              <span className={styles.sidebarItem}>Inactive item</span>
              <span
                className={`${styles.sidebarItem} ${styles.sidebarItemActive}`}
              >
                Current page
              </span>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>
              Status badges &amp; file tree rows
            </h2>
            <div className={styles.row}>
              {statusBadges.map((b) => (
                <span
                  key={b.label}
                  className={styles.badge}
                  style={{
                    background: b.bg,
                    boxShadow: `inset 0 0 0 1px ${b.ring}`,
                    color: b.color,
                  }}
                >
                  <span
                    className={styles.badgeDot}
                    style={{ background: b.color }}
                  />
                  {b.label}
                </span>
              ))}
            </div>
            <div className={styles.fileList}>
              {fileRows.map((f) => (
                <div
                  key={f.name}
                  className={[
                    styles.fileRow,
                    f.dim ? styles.fileRowDim : "",
                    f.selected ? styles.fileRowSelected : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span className={styles.fileIcon}>{f.icon}</span>
                  <span>{f.name}</span>
                  {f.tag ? (
                    <span
                      className={styles.fileTag}
                      style={{ color: f.tagColor }}
                    >
                      {f.tag}
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Cards</h2>
            <div className={styles.cardPair}>
              <div className={styles.demoCard}>
                <span className={styles.demoCardLabel}>01</span>
                <span className={styles.demoCardTitle}>Default card</span>
                <span className={styles.demoCardBody}>
                  Surface 1 on page background, 1px border, radius 10.
                </span>
              </div>
              <div className={`${styles.demoCard} ${styles.demoCardAccent}`}>
                <span className={styles.demoCardLabel}>FEATURED</span>
                <span className={styles.demoCardTitle}>Accented card</span>
                <span className={styles.demoCardBody}>
                  Warm border only — never an orange fill behind body text.
                </span>
              </div>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Code block</h2>
            <CodeBlock label="shell" copyText={SHELL} density="dense">
              <div>
                <span className={code.ok}>$</span> python -m pip install -e .
              </div>
              <div>
                <span className={code.ok}>$</span> lunar-forge --docker{" "}
                <span className={code.str}>&quot;Explain this project&quot;</span>
              </div>
              <div className={code.dim}>
                {"  "}project config: .agent/config.yaml
              </div>
            </CodeBlock>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Documentation callouts</h2>
            <div className={styles.col}>
              {calloutSamples.map((c) => (
                <Callout key={c.kind} kind={c.kind}>
                  {c.body}
                </Callout>
              ))}
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>
              Chat message &amp; progress block
            </h2>
            <div className={styles.chatSample}>
              <div>
                <div className={styles.chatSpeaker}>You:</div>
                <div className={styles.chatUser}>
                  Review the project without editing files.
                </div>
              </div>
              <div className={styles.col} style={{ gap: 8 }}>
                <div className={styles.chatSpeaker}>LunarForge:</div>
                <div className={styles.chatAgent}>
                  Reading the project in review-only mode. No file tools will
                  write.
                </div>
                <div className={styles.chatTool}>
                  <span className={styles.chatToolKind}>read</span>
                  <span className={styles.chatToolName}>app/page.tsx</span>
                  <span className={styles.chatToolTime}>0.4s</span>
                </div>
                <div className={styles.chatProgress}>
                  <span className={styles.chatProgressDot} />
                  Inspecting project · 00:12
                </div>
              </div>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Dialog</h2>
            <div className={styles.dialog}>
              <div className={styles.dialogHead}>
                <div className={styles.dialogTitle}>Reset this sandbox?</div>
                <p className={styles.dialogBody}>
                  The container and all file changes are destroyed. The
                  transcript stays available.
                </p>
              </div>
              <div className={styles.dialogActions}>
                <Button variant="outline">Cancel</Button>
                <Button variant="destructive">Reset sandbox</Button>
              </div>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Approval panel</h2>
            <div className={styles.approval}>
              <div className={styles.approvalHead}>
                <span className={styles.approvalTitle}>
                  Run command in sandbox
                </span>
                <span className={styles.approvalRisk}>risk: medium</span>
              </div>
              <div className={styles.approvalCommand}>
                npm run validate -- --reporter=json --max-warnings=0
              </div>
              <div className={styles.approvalActions}>
                <Button variant="secondary" size="md">
                  Deny
                </Button>
                <Button variant="primary" size="md">
                  Approve
                </Button>
              </div>
            </div>
          </div>

          <div className={styles.specimen}>
            <h2 className={styles.specimenTitle}>Toasts &amp; banners</h2>
            <div className={styles.col}>
              {toasts.map((t) => (
                <div
                  key={t.title}
                  className={styles.toast}
                  style={{
                    background: t.bg,
                    border: `1px solid ${t.ring}`,
                  }}
                >
                  <span
                    className={styles.toastDot}
                    style={{ background: t.color }}
                  />
                  <span className={styles.toastCopy}>
                    <span className={styles.toastTitle}>{t.title}</span>
                    <span className={styles.toastBody}>{t.body}</span>
                  </span>
                  <span
                    className={styles.toastAction}
                    style={{ color: t.color }}
                  >
                    {t.action}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---------- Interaction notes ---------- */}
        <section className={styles.notesPanel} aria-label="Interaction notes">
          <div className={styles.intro}>
            <p className={styles.panelLabel}>
              Interaction &amp; responsive notes
            </p>
            <p className={styles.blurb}>
              Implementation contract for the Next.js frontend and the future
              FastAPI-backed sandbox. Sandbox states remain deterministic UI
              fixtures until that integration is connected.
            </p>
          </div>

          <div className={styles.block}>
            <p className={styles.sidebarGroup} style={{ padding: 0 }}>
              Breakpoints
            </p>
            <div className={styles.breakpointGrid}>
              {breakpoints.map((b) => (
                <div key={b.range} className={styles.breakpoint}>
                  <span className={styles.breakpointRange}>{b.range}</span>
                  <span className={styles.breakpointName}>{b.name}</span>
                  <span className={styles.breakpointBody}>{b.description}</span>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.noteColumns}>
            {interactionNotes.map((column, i) => (
              <div key={i}>
                {column.map(([name, body]) => (
                  <div key={name} className={styles.noteRow}>
                    <span className={styles.noteName}>{name}</span>
                    <span className={styles.noteBody}>{body}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        {/* ---------- Sandbox state matrix ---------- */}
        <section className={styles.notesPanel} aria-label="Sandbox states">
          <div className={styles.intro}>
            <p className={styles.panelLabel}>Sandbox states</p>
            <p className={styles.blurb}>
              Target state fixtures rendered in the chat column; the header
              status pill and input controls change with each state. They define
              the integration contract and are not evidence of a live backend.
            </p>
          </div>
          <div className={styles.stateGrid}>
            {sandboxStates.map((s) => (
              <article key={s.key} className={styles.stateCard}>
                <div className={styles.stateHead}>
                  <span className={styles.stateName}>
                    <span
                      className={styles.stateDot}
                      style={{ background: TONE_COLOR[s.tone] }}
                    />
                    {s.title}
                  </span>
                  <span className={styles.stateKey}>{s.key}</span>
                </div>
                <div className={styles.stateBody}>
                  <div
                    className={styles.statePreview}
                    style={{
                      boxShadow: `inset 0 0 0 1px ${TONE_RING[s.tone]}`,
                    }}
                  >
                    <span
                      className={styles.stateLine}
                      style={{ color: TONE_COLOR[s.tone] }}
                    >
                      {s.line}
                    </span>
                    <span className={styles.stateText}>{s.body}</span>
                    {s.progress ? (
                      <span className={styles.stateBar}>
                        <span
                          className={styles.stateBarFill}
                          style={{
                            width: s.progress,
                            background: TONE_COLOR[s.tone],
                          }}
                        />
                      </span>
                    ) : null}
                  </div>
                  <div className={styles.stateActions}>
                    {s.actions.map((a) => (
                      <Button
                        key={a.label}
                        variant={a.kind === "secondary" ? "outline" : a.kind}
                        size="sm"
                      >
                        {a.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
