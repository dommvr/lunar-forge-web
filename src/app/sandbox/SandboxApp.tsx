"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  activityLog,
  activeMeta,
  APPROVAL_COMMAND,
  approvalMeta,
  examplePrompts,
  panelTabs,
  PRICING_PREVIEW,
  projectTree,
  readyMeta,
  toolRows,
  usageRows,
  validationSteps,
  type ActivityEvent,
  type PanelTab,
} from "@/lib/sandbox";

import styles from "./sandbox.module.css";

type Phase =
  | "ready"
  | "running"
  | "gated"
  | "validating"
  | "done"
  | "cancelled";

type Message = { id: number; role: "user" | "agent"; text: string };

const STATUS: Record<Phase, { label: string; tone: string }> = {
  ready: { label: "Ready", tone: styles.toneSuccess },
  running: { label: "Agent working", tone: styles.toneAccent },
  gated: { label: "Waiting for approval", tone: styles.toneWarning },
  validating: { label: "Running validation", tone: styles.toneAccent },
  done: { label: "Task completed", tone: styles.toneSuccess },
  cancelled: { label: "Task stopped", tone: styles.toneMuted },
};

const KIND_CLASS = {
  read: styles.kindRead,
  edit: styles.kindEdit,
  run: styles.kindRun,
} as const;

const CHECK_CLASS = {
  success: styles.iconSuccess,
  warning: styles.iconWarning,
  faint: styles.iconFaint,
} as const;

const clock = (seconds: number) =>
  `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

export function SandboxApp() {
  const [phase, setPhase] = useState<Phase>("ready");
  const [messages, setMessages] = useState<Message[]>([]);
  const [visibleTools, setVisibleTools] = useState(0);
  const [progress, setProgress] = useState<string | null>(null);
  const [checksDone, setChecksDone] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [draft, setDraft] = useState("");
  const [tab, setTab] = useState<PanelTab>("Activity");
  const [segment, setSegment] = useState<"Chat" | "Files" | "Events">("Chat");
  const [events, setEvents] = useState<ActivityEvent[]>(activityLog);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const denyRef = useRef<HTMLButtonElement>(null);
  const nextId = useRef(0);

  const clearTimers = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  const after = useCallback((ms: number, fn: () => void) => {
    timers.current.push(setTimeout(fn, ms));
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const say = useCallback((role: Message["role"], text: string) => {
    nextId.current += 1;
    /* Read the id here, not inside the updater: two say() calls batched in the
     * same tick would otherwise both see the final ref value and collide. */
    const id = nextId.current;
    setMessages((m) => [...m, { id, role, text }]);
  }, []);

  const emit = useCallback((event: ActivityEvent) => {
    setEvents((e) => [...e, event]);
  }, []);

  const started = messages.length > 0;
  const changed = visibleTools >= 3;
  const busy = phase === "running" || phase === "validating";
  const tree = useMemo(() => projectTree(changed), [changed]);

  /* Elapsed clock while a task is in flight. */
  useEffect(() => {
    if (phase === "ready" || phase === "done" || phase === "cancelled") return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [phase]);

  /* Streaming text appends without layout shift; keep the tail in view. */
  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, visibleTools, phase]);

  /* Focus moves to Deny — the safe default — when the gate opens. */
  useEffect(() => {
    if (phase === "gated") denyRef.current?.focus();
  }, [phase]);

  const run = useCallback(
    (prompt: string) => {
      clearTimers();
      setElapsed(0);
      setChecksDone(0);
      setVisibleTools(0);
      setPhase("running");
      say("user", prompt);
      emit({
        name: "task.started",
        detail: prompt.slice(0, 42),
        time: "0.0s",
        tone: "muted",
      });
      setProgress("Inspecting project · 12 files matched · reading AGENTS.md");

      after(700, () => {
        setVisibleTools(1);
        emit({
          name: "tool.read",
          detail: "AGENTS.md · root + app/",
          time: "0.3s",
          tone: "success",
        });
      });
      after(1200, () => {
        setVisibleTools(2);
        setProgress("Planning changes · 3 edits");
      });
      after(2100, () => {
        setVisibleTools(3);
        emit({
          name: "tool.edit",
          detail: "components/Pricing.tsx · new file",
          time: "1.2s",
          tone: "success",
        });
        say(
          "agent",
          "I read AGENTS.md and the marketing route, added a three-tier pricing section with a mobile stack, and wired it into the page. Next I need to run the project's validation command.",
        );
      });
      after(2900, () => {
        setVisibleTools(4);
        setPhase("gated");
        setProgress(null);
        emit({
          name: "approval.requested",
          detail: "command.run · risk medium",
          time: "2.9s",
          tone: "muted",
        });
      });
    },
    [after, clearTimers, emit, say],
  );

  const approve = useCallback(() => {
    clearTimers();
    setPhase("validating");
    setTab("Validation");
    emit({
      name: "approval.resolved",
      detail: "approved · npm run validate",
      time: "3.0s",
      tone: "success",
    });
    setProgress("Running validation · step 1 of 5");

    validationSteps.forEach((step, i) => {
      after(700 * (i + 1), () => {
        setChecksDone(i + 1);
        setProgress(`Running validation · step ${i + 1} of ${validationSteps.length}`);
      });
    });

    after(700 * (validationSteps.length + 1), () => {
      setPhase("done");
      setProgress(null);
      emit({
        name: "task.completed",
        detail: "3 files changed · validation passed",
        time: "41s",
        tone: "success",
      });
      say("agent", "Edited 3 files. Validation passed in 41s.");
      say(
        "agent",
        "Staged summary — feat(marketing): responsive pricing section",
      );
    });
  }, [after, clearTimers, emit, say]);

  const deny = useCallback(() => {
    clearTimers();
    setPhase("cancelled");
    setProgress(null);
    emit({
      name: "approval.resolved",
      detail: "denied · task stopped",
      time: "3.0s",
      tone: "muted",
    });
    say(
      "agent",
      "Denied. The task is stopped and nothing was executed — the three file edits are kept so you can review them.",
    );
  }, [clearTimers, emit, say]);

  const stop = useCallback(() => {
    clearTimers();
    setPhase("cancelled");
    setProgress(null);
    say(
      "agent",
      "Task stopped. Uncommitted edits from this task were rolled back: components/Pricing.tsx removed, app/page.tsx and package.json restored.",
    );
  }, [clearTimers, say]);

  const reset = useCallback(() => {
    clearTimers();
    setPhase("ready");
    setMessages([]);
    setVisibleTools(0);
    setProgress(null);
    setChecksDone(0);
    setElapsed(0);
    setDraft("");
    setTab("Activity");
    setEvents(activityLog);
  }, [clearTimers]);

  const submit = () => {
    const text = draft.trim();
    if (!text || phase === "gated" || busy) return;
    setDraft("");
    run(text);
  };

  const status = STATUS[phase];
  const meta = phase === "ready" ? readyMeta : activeMeta;
  const gated = phase === "gated";

  /* ---------- Fragments shared between desktop and mobile ---------- */

  const filesPanel = (
    <section className={styles.filesPanel} aria-label="Project files">
      <div className={styles.panelHead}>
        <span className={styles.panelLabel}>Project</span>
        {changed ? (
          <span className={styles.changedCount}>3 changed</span>
        ) : (
          <span className={styles.panelActions} aria-hidden="true">
            <span>↻</span>
            <span>⟨⟩</span>
          </span>
        )}
      </div>
      <div className={styles.tree}>
        {tree.map((f) => (
          <div
            key={f.name}
            className={[
              styles.treeRow,
              f.level === 0 ? styles.treeRowRoot : "",
              f.tag ? styles.treeRowHot : "",
              changed && f.name === "Pricing.tsx" ? styles.treeRowSelected : "",
            ]
              .filter(Boolean)
              .join(" ")}
            style={{ paddingLeft: 8 + f.level * 14 }}
          >
            <span className={styles.treeIcon}>{f.icon}</span>
            <span className={styles.treeName}>{f.name}</span>
            {f.tag ? (
              <span
                className={`${styles.treeTag} ${f.tag === "A" ? styles.tagAdded : styles.tagModified}`}
              >
                {f.tag}
              </span>
            ) : null}
          </div>
        ))}
      </div>

      {changed ? (
        <div className={styles.previewPane}>
          <div className={styles.previewHead}>Pricing.tsx · preview</div>
          <pre className={styles.previewCode}>
            {PRICING_PREVIEW.slice(0, 3).map((line) => (
              <div key={line} className={styles.diffAdd}>
                {line}
              </div>
            ))}
            <div>    ...</div>
          </pre>
        </div>
      ) : (
        <div className={styles.filesFoot}>
          <div className={styles.filesFootLabel}>read-only · sandbox copy</div>
          <div className={styles.filesFootBody}>
            Edits apply to the ephemeral sandbox project only.
          </div>
        </div>
      )}
    </section>
  );

  const detailsPanel = (
    <section className={styles.detailsPanel} aria-label="Session details">
      <div className={styles.tabsWrap}>
        <div className={styles.tabs} role="tablist">
          {panelTabs.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={t === tab}
              className={`${styles.tab} ${t === tab ? styles.tabActive : ""}`}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className={styles.detailsBody}>
        {tab === "Activity" ? (
          <>
            <div className={styles.panelLabel}>Activity</div>
            {events.map((e, i) => (
              <div key={`${e.name}-${i}`} className={styles.activityRow}>
                <span
                  className={`${styles.activityDot} ${e.tone === "success" ? styles.dotSuccess : styles.dotMuted}`}
                />
                <span className={styles.activityText}>
                  <span className={styles.activityName}>{e.name}</span>
                  <span className={styles.activityDetail}>{e.detail}</span>
                </span>
                <span className={styles.activityTime}>{e.time}</span>
              </div>
            ))}
          </>
        ) : null}

        {tab === "Validation" ? (
          started ? (
            <>
              <div className={styles.progressCard}>
                <div className={styles.progressCardHead}>
                  <span className={styles.progressCardTitle}>Validation</span>
                  <span className={styles.progressCardState}>
                    {gated
                      ? "pending approval"
                      : phase === "done"
                        ? "passed"
                        : phase === "cancelled"
                          ? "stopped"
                          : "running"}
                  </span>
                </div>
                <div className={styles.bar}>
                  <div
                    className={styles.barFill}
                    style={{
                      width: `${gated ? 62 : (checksDone / validationSteps.length) * 100}%`,
                    }}
                  />
                </div>
                <div className={styles.progressCardMeta}>
                  {gated ? 3 : checksDone} of {validationSteps.length} steps ·{" "}
                  {clock(elapsed)} elapsed
                </div>
              </div>
              {validationSteps.map((v, i) => {
                const complete = i < checksDone;
                return (
                  <div key={v.name} className={styles.checkRow}>
                    <span
                      className={`${styles.checkIcon} ${complete ? styles.iconSuccess : CHECK_CLASS[v.tone]}`}
                    >
                      {complete ? "✓" : v.icon}
                    </span>
                    <span className={styles.checkName}>{v.name}</span>
                    <span className={styles.checkDetail}>
                      {complete ? v.detail : gated ? "gated" : "queued"}
                    </span>
                  </div>
                );
              })}
            </>
          ) : (
            <div className={styles.emptyState}>
              No validation runs yet.
              <br />
              Ask for a change, then approve the command.
            </div>
          )
        ) : null}

        {tab === "Artifacts" ? (
          <div className={styles.emptyState}>
            {phase === "done"
              ? "validation-8f3c2a.json · 4.1 KB"
              : "No artifacts yet."}
            <br />
            Artifacts appear here after a task.
          </div>
        ) : null}

        {tab === "Usage" ? (
          <div className={styles.usageCard}>
            <div className={styles.panelLabel}>Usage</div>
            {usageRows.map((u) => (
              <div key={u.k} className={styles.usageRow}>
                <span className={styles.usageKey}>{u.k}</span>
                <span className={styles.usageValue}>{u.v}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );

  const approvalPanel = (
    <section
      className={styles.approval}
      aria-live="assertive"
      aria-label="Approval required"
    >
      <div className={styles.approvalHead}>
        <div>
          <div className={styles.approvalTitle}>Run command in sandbox</div>
          <div className={styles.approvalSub}>
            Executes the project&apos;s validation command inside the container.
            No network access.
          </div>
        </div>
        <span className={styles.riskChip}>risk: medium</span>
      </div>
      <div className={styles.approvalDetails}>
        <div className={styles.approvalCommand}>{APPROVAL_COMMAND}</div>
        <div className={styles.approvalMeta}>
          {approvalMeta.map((m) => (
            <div key={m.k} style={{ display: "contents" }}>
              <span className={styles.approvalMetaKey}>{m.k}</span>
              <span className={styles.approvalMetaValue}>{m.v}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={styles.approvalActions}>
        <span className={styles.approvalHint}>
          Denying stops the task and keeps file edits.
        </span>
        <div className={styles.approvalButtons}>
          <Button ref={denyRef} variant="secondary" onClick={deny}>
            Deny
          </Button>
          <Button
            variant="primary"
            className={styles.approveFocus}
            onClick={approve}
          >
            Approve
          </Button>
        </div>
      </div>
    </section>
  );

  const chat = (
    <section className={styles.chat} aria-label="Transcript">
      <div className={styles.transcript} ref={transcriptRef}>
        {!started ? (
          <div className={styles.onboarding}>
            <div>
              <div className={styles.onboardingTitle}>
                A disposable session, ready to go
              </div>
              <p className={styles.onboardingBody}>
                A small Next.js sample project is loaded. Commands run inside
                the sandbox container and still pause for your approval. Nothing
                touches your machine.
              </p>
            </div>
            <div>
              <div className={styles.panelLabel}>Try one of these</div>
              <div className={styles.promptGrid} style={{ marginTop: 8 }}>
                {examplePrompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={styles.promptButton}
                    onClick={() => run(p)}
                  >
                    <span className={styles.promptArrow}>→</span>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : null}

        {!started ? (
          <div className={styles.message}>
            <div className={styles.speaker}>LunarForge:</div>
            <p className={styles.agentText}>
              Sandbox provisioned in 3.1s. The project is at{" "}
              <code className={styles.inlineCode}>/workspace/sample-app</code>.
              Ask me to explain it, change it, or run its checks — I will show
              you each command before it runs.
            </p>
          </div>
        ) : null}

        {messages.map((m) => (
          <div key={m.id} className={styles.message}>
            <div className={styles.speaker}>
              {m.role === "user" ? "You:" : "LunarForge:"}
            </div>
            <p className={m.role === "user" ? styles.userText : styles.agentText}>
              {m.text}
            </p>
          </div>
        ))}

        {visibleTools > 0 ? (
          <div className={styles.toolList}>
            {toolRows.slice(0, visibleTools).map((t) => (
              <div key={t.name} className={styles.toolRow}>
                <span className={`${styles.toolKind} ${KIND_CLASS[t.kind]}`}>
                  {t.kind}
                </span>
                <span className={styles.toolName}>{t.name}</span>
                <span className={styles.toolArg}>{t.arg}</span>
                <span className={styles.toolTime}>{t.time}</span>
              </div>
            ))}
          </div>
        ) : null}

        <div className={styles.progressLine} aria-live="polite">
          {progress ? (
            <>
              <span className={styles.progressDot} />
              {progress} · {clock(elapsed)}
            </>
          ) : gated ? (
            <>
              <span className={styles.progressDot} />
              Waiting for approval · {clock(elapsed)}
            </>
          ) : null}
        </div>

        {gated ? approvalPanel : null}
      </div>

      {gated ? (
        <div className={styles.sheet}>
          <div className={styles.sheetHead}>
            <div>
              <div className={styles.sheetTitle}>Run command in sandbox</div>
              <div className={styles.sheetSub}>
                Runs the project&apos;s validation command. No network.
              </div>
            </div>
            <span className={styles.sheetRisk}>medium</span>
          </div>
          <div className={styles.sheetCommand}>{APPROVAL_COMMAND}</div>
          <div className={styles.sheetActions}>
            <Button variant="secondary" size="block" onClick={deny}>
              Deny
            </Button>
            <Button variant="primary" size="block" onClick={approve}>
              Approve
            </Button>
          </div>
        </div>
      ) : null}

      <div className={styles.composerWrap}>
        <div
          className={`${styles.composer} ${gated ? styles.composerPaused : ""}`}
        >
          <textarea
            className={styles.input}
            rows={1}
            value={draft}
            disabled={gated}
            placeholder={
              gated
                ? "Input paused while an approval is pending…"
                : "Ask LunarForge to do something in this project…"
            }
            aria-label="Message LunarForge"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <div className={styles.composerRow}>
            <div className={styles.composerFlags}>
              <span className={styles.flag}>Compact context</span>
              {!gated ? <span className={styles.flag}>effort: medium</span> : null}
            </div>
            <div className={styles.composerSend}>
              {busy || gated ? (
                <Button variant="destructive" onClick={stop}>
                  Stop task
                </Button>
              ) : (
                <span className={styles.hint}>⏎ send · ⇧⏎ newline</span>
              )}
              <Button
                variant="primary"
                onClick={submit}
                disabled={gated || busy || draft.trim().length === 0}
              >
                Send
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );

  return (
    <div className={styles.app} id="main">
      <h1 className="srOnly">LunarForge sandbox</h1>

      {/* Desktop header */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <Link href="/" className={styles.brand}>
            <span className={styles.mark} aria-hidden="true" />
            <span className={styles.brandName}>LunarForge</span>
          </Link>
          <span className={styles.divider} aria-hidden="true" />
          <span
            className={`${styles.statusPill} ${status.tone}`}
            role="status"
          >
            <span className={styles.statusDot} />
            {status.label}
          </span>
        </div>
        <div className={styles.headerRight}>
          <div className={styles.metaChips}>
            {meta.map((m) => (
              <span key={m.k} className={styles.chip}>
                <span className={styles.chipKey}>{m.k}</span>
                <span
                  className={`${styles.chipValue} ${m.hot ? styles.chipHot : ""}`}
                >
                  {m.v}
                </span>
              </span>
            ))}
          </div>
          <Button variant="outline" onClick={reset}>
            Reset sandbox
          </Button>
        </div>
      </header>

      {/* Mobile header */}
      <header className={styles.mobileHeader}>
        <div className={styles.mobileHeaderTop}>
          <div className={styles.headerLeft}>
            <Link href="/" className={styles.brand}>
              <span className={styles.mark} aria-hidden="true" />
              <span className={styles.brandName}>Sandbox</span>
            </Link>
            <span className={`${styles.statusPill} ${status.tone}`}>
              <span className={styles.statusDot} />
              {status.label}
            </span>
          </div>
          <Button variant="outline" size="sm" onClick={reset}>
            Reset
          </Button>
        </div>
        <div className={styles.mobileChips}>
          {meta.slice(0, 4).map((m) => (
            <span key={m.k} className={styles.chip}>
              {m.v}
            </span>
          ))}
        </div>
        <div className={styles.segmented} role="tablist">
          {(["Chat", "Files", "Events"] as const).map((s) => (
            <button
              key={s}
              type="button"
              role="tab"
              aria-selected={s === segment}
              className={`${styles.segment} ${s === segment ? styles.segmentActive : ""}`}
              onClick={() => setSegment(s)}
            >
              {s}
              {s === "Files" && changed ? (
                <span className={styles.segmentCount}> 3</span>
              ) : null}
            </button>
          ))}
        </div>
      </header>

      <div
        className={`${styles.grid} ${segment !== "Chat" ? styles.gridPushed : ""}`}
      >
        {filesPanel}
        {chat}
        {detailsPanel}
      </div>

      {/* Mobile panels replace the grid below 768. */}
      {segment !== "Chat" ? (
        <div className={styles.mobilePanel}>
          {segment === "Files" ? filesPanel : detailsPanel}
        </div>
      ) : null}
    </div>
  );
}
