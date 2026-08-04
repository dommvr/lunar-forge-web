"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { LogoutButton } from "@/components/auth/LogoutButton";
import { Button } from "@/components/ui/Button";
import {
  APPROVAL_COMMAND,
  examplePrompts,
  panelTabs,
  type PanelTab,
} from "@/lib/sandbox";

import {
  useSandboxSession,
  type FundingSelection,
  type UseSandboxSessionOptions,
} from "./hooks/useSandboxSession";
import type { SandboxPhase } from "./state/sandboxReducer";

import styles from "./sandbox.module.css";

const STATUS: Record<SandboxPhase, { label: string; tone: string }> = {
  idle: { label: "No sandbox", tone: styles.toneMuted },
  provisioning: { label: "Provisioning", tone: styles.toneWarning },
  ready: { label: "Ready", tone: styles.toneSuccess },
  running: { label: "Agent working", tone: styles.toneAccent },
  gated: { label: "Waiting for approval", tone: styles.toneWarning },
  validating: { label: "Running validation", tone: styles.toneAccent },
  done: { label: "Task completed", tone: styles.toneSuccess },
  cancelled: { label: "Task stopped", tone: styles.toneMuted },
  expired: { label: "Sandbox expired", tone: styles.toneMuted },
  limited: { label: "Usage limit reached", tone: styles.toneWarning },
  offline: { label: "Reconnecting", tone: styles.toneWarning },
  error: { label: "Recoverable error", tone: styles.toneError },
  fatal: { label: "Sandbox error", tone: styles.toneError },
};

const clock = (seconds: number) =>
  `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

export type SandboxAppProps = UseSandboxSessionOptions;

export function SandboxApp(props: SandboxAppProps = {}) {
  const controller = useSandboxSession(props);
  const { state } = controller;
  const phase = state.phase;
  const messages = state.messages;
  const visibleTools = state.visibleTools;
  const progress = state.progress;
  const checksDone = state.checksDone;
  const validationComplete = checksDone > 0;
  const events = state.activities;
  const displayedTools = events
    .filter((event) => event.name === "tool.started")
    .slice(-4);
  const changed = state.changed;
  const [elapsed, setElapsed] = useState(0);
  const [draft, setDraft] = useState("");
  const [tab, setTab] = useState<PanelTab>("Activity");
  const [segment, setSegment] = useState<"Chat" | "Files" | "Events">("Chat");
  const [funding, setFunding] = useState<FundingSelection>({
    fundingMode: "owner_funded",
    provider: "openai",
  });
  /* Provider credentials intentionally live only in component memory. */
  const [byokKey, setByokKey] = useState("");
  const transcriptRef = useRef<HTMLDivElement>(null);
  const denyRef = useRef<HTMLButtonElement>(null);
  const mobileDenyRef = useRef<HTMLButtonElement>(null);
  const [now, setNow] = useState(() => Date.now());

  const started = messages.length > 0;
  const busy = phase === "running" || phase === "validating";
  const tree = useMemo(
    () =>
      (state.files?.items ?? []).map((file) => {
        const parts = file.path.split("/");
        return {
          ...file,
          name: parts.at(-1) ?? file.path,
          level: Math.max(0, parts.length - 1),
          icon: file.kind === "directory" ? "▸" : "·",
          tag: state.changedPaths.includes(file.path) ? "M" : null,
        };
      }),
    [state.changedPaths, state.files],
  );
  const remainingSeconds = state.expiresAt
    ? Math.max(0, Math.ceil((new Date(state.expiresAt).getTime() - now) / 1000))
    : 30 * 60;
  const byokInvalid = funding.fundingMode === "byok" && byokKey.length < 8;

  /* This clock reports elapsed real time; it never drives a state transition. */
  useEffect(() => {
    if (phase === "running") setElapsed(0);
    if (phase === "expired" || phase === "idle") setByokKey("");
  }, [phase]);

  useEffect(() => {
    if (!busy && phase !== "gated") return;
    const id = setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => clearInterval(id);
  }, [busy, phase]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  /* Streaming text appends without layout shift; keep the tail in view. */
  useEffect(() => {
    const element = transcriptRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages, visibleTools, phase]);

  /* Focus moves to Deny — the safe default — when the gate opens. */
  useEffect(() => {
    if (phase !== "gated") return;
    const mobile = window.matchMedia?.("(max-width: 767px)").matches ?? false;
    (mobile ? mobileDenyRef.current : denyRef.current)?.focus();
  }, [phase]);

  const run = (prompt: string) => {
    if (!state.sessionId || busy || phase === "gated" || byokInvalid) return;
    void controller.submit(
      prompt,
      funding,
      funding.fundingMode === "byok" ? byokKey : undefined,
    );
  };

  const approve = () => {
    setTab("Validation");
    void controller.resolveApproval(true);
  };

  const deny = () => void controller.resolveApproval(false);
  const stop = () => void controller.cancel();

  const reset = () => {
    setElapsed(0);
    setDraft("");
    setTab("Activity");
    setByokKey("");
    void controller.reset();
  };

  const remove = () => {
    setByokKey("");
    void controller.deleteSandbox();
  };

  const submit = () => {
    const text = draft.trim();
    if (!text || phase === "gated" || busy || byokInvalid) return;
    setDraft("");
    run(text);
  };

  const status = STATUS[phase];
  const meta = [
    { k: "session", v: state.sessionId?.slice(0, 12) ?? "starting" },
    { k: "runtime", v: state.runtimeProvider ?? "starting" },
    {
      k: "model",
      v:
        funding.fundingMode === "byok"
          ? `${funding.provider} · BYOK`
          : "OpenAI · server-approved",
    },
    { k: "effort", v: "medium" },
    { k: "network", v: "denied" },
    { k: "time left", v: clock(remainingSeconds), hot: remainingSeconds < 300 },
  ];
  const gated = phase === "gated";
  const currentApproval = state.approval;
  const currentApprovalMeta = [
    { k: "runtime", v: `${state.runtimeProvider ?? "sandbox"} · network denied` },
    { k: "cwd", v: "sandbox workspace" },
    { k: "scope", v: "owned sandbox project" },
    { k: "requested by", v: "LunarForge agent" },
  ];

  /* ---------- Fragments shared between desktop and mobile ---------- */

  const filesPanel = (
    <section className={styles.filesPanel} aria-label="Project files">
      <div className={styles.panelHead}>
        <span className={styles.panelLabel}>Project</span>
        {changed ? (
          <span className={styles.changedCount}>
            {state.changedPaths.length} changed
          </span>
        ) : (
          <span className={styles.panelActions} aria-hidden="true">
            <span>↻</span>
            <span>⟨⟩</span>
          </span>
        )}
      </div>
      <div className={styles.tree}>
        {tree.length === 0 ? (
          <div className={styles.emptyState}>No project files available.</div>
        ) : null}
        {tree.map((f) => (
          <button
            type="button"
            key={f.path}
            disabled={f.kind !== "file"}
            onClick={() => void controller.openFile(f.path)}
            className={[
              styles.treeRow,
              f.level === 0 ? styles.treeRowRoot : "",
              f.tag ? styles.treeRowHot : "",
              state.selectedFile?.path === f.path ? styles.treeRowSelected : "",
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
          </button>
        ))}
      </div>

      {state.selectedFile ? (
        <div className={styles.previewPane}>
          <div className={styles.previewHead}>
            {state.selectedFile.path} · {state.selectedFile.truncated ? "truncated" : "preview"}
          </div>
          <pre className={styles.previewCode}>
            {state.selectedFile.content}
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
                      width: `${gated ? 0 : validationComplete ? 100 : 45}%`,
                    }}
                  />
                </div>
                <div className={styles.progressCardMeta}>
                  {validationComplete ? 1 : 0} of 1 checks ·{" "}
                  {clock(elapsed)} elapsed
                </div>
                {state.validationMessage ? (
                  <div className={styles.progressCardMeta}>{state.validationMessage}</div>
                ) : null}
              </div>
              <div className={styles.checkRow}>
                <span
                  className={`${styles.checkIcon} ${validationComplete ? styles.iconSuccess : styles.iconFaint}`}
                >
                  {validationComplete ? "✓" : "·"}
                </span>
                <span className={styles.checkName}>Project validation</span>
                <span className={styles.checkDetail}>
                  {validationComplete
                    ? state.validationMessage ?? "passed"
                    : gated
                      ? "gated"
                      : "queued"}
                </span>
              </div>
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
          state.artifacts.length > 0 ? (
            <div className={styles.artifactList}>
              {state.artifacts.map((artifact) => (
                <div className={styles.artifactRow} key={artifact.id}>
                  <span>
                    <strong>{artifact.name}</strong>
                    <small>{(artifact.size_bytes / 1024).toFixed(1)} KB · {artifact.media_type}</small>
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    aria-label={`Download ${artifact.name}`}
                    onClick={() => void controller.downloadArtifact(artifact.id)}
                  >
                    Download
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              No artifacts yet.
              <br />
              Artifacts appear here after a task.
            </div>
          )
        ) : null}

        {tab === "Usage" ? (
          <div className={styles.usageCard}>
            <div className={styles.panelLabel}>Usage</div>
            {[
              { k: "input tokens", v: state.usageInputTokens.toLocaleString() },
              { k: "output tokens", v: state.usageOutputTokens.toLocaleString() },
              { k: "estimated cost", v: `$${state.usageEstimatedCost.toFixed(4)}` },
              { k: "replay sequence", v: `#${state.lastSequence}` },
            ].map((u) => (
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
          <div className={styles.approvalTitle}>
            {currentApproval?.title ?? "Run command in sandbox"}
          </div>
          <div className={styles.approvalSub}>
            {currentApproval?.summary ??
              "Executes the project's validation command. No network access."}
          </div>
        </div>
        <span className={styles.riskChip}>
          risk: {currentApproval?.risk ?? "medium"}
        </span>
      </div>
      <div className={styles.approvalDetails}>
        <div className={styles.approvalCommand}>
          {currentApproval?.details ?? APPROVAL_COMMAND}
        </div>
        <div className={styles.approvalMeta}>
          {currentApprovalMeta.map((m) => (
            <div key={m.k} style={{ display: "contents" }}>
              <span className={styles.approvalMetaKey}>{m.k}</span>
              <span className={styles.approvalMetaValue}>{m.v}</span>
            </div>
          ))}
        </div>
      </div>
      <div className={styles.approvalActions}>
        <span className={styles.approvalHint}>
          Denying rejects this action. Stop task requests current-turn rollback.
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
                Interactive sandbox, ready to go
              </div>
              <p className={styles.onboardingBody}>
                A private project runtime is connected through the authenticated
                control plane. Structured events, approvals, files, artifacts,
                and downloads stay scoped to this active sandbox.
              </p>
            </div>
            <fieldset className={styles.fundingCard}>
              <legend className={styles.panelLabel}>Funding and provider</legend>
              <div className={styles.fundingOptions}>
                <label className={styles.fundingOption}>
                  <input
                    type="radio"
                    name="funding-mode"
                    value="owner_funded"
                    checked={funding.fundingMode === "owner_funded"}
                    onChange={() => {
                      setFunding({ fundingMode: "owner_funded", provider: "openai" });
                      setByokKey("");
                    }}
                  />
                  <span>
                    <strong>Owner-funded</strong>
                    <small>Server-approved OpenAI model and limits.</small>
                  </span>
                </label>
                <label className={styles.fundingOption}>
                  <input
                    type="radio"
                    name="funding-mode"
                    value="byok"
                    checked={funding.fundingMode === "byok"}
                    onChange={() =>
                      setFunding({ fundingMode: "byok", provider: "openai" })
                    }
                  />
                  <span>
                    <strong>Bring your own key</strong>
                    <small>Sent only with each private turn request.</small>
                  </span>
                </label>
              </div>
              {funding.fundingMode === "byok" ? (
                <div className={styles.byokFields}>
                  <label>
                    <span>Provider</span>
                    <select
                      aria-label="BYOK provider"
                      value={funding.provider}
                      onChange={(event) =>
                        setFunding({
                          fundingMode: "byok",
                          provider: event.target.value as "openai" | "anthropic",
                        })
                      }
                    >
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                    </select>
                  </label>
                  <label>
                    <span>Provider key</span>
                    <input
                      aria-label="Provider key"
                      type="password"
                      autoComplete="off"
                      spellCheck={false}
                      value={byokKey}
                      onChange={(event) => setByokKey(event.target.value)}
                      placeholder="Held in memory until you leave this page"
                    />
                  </label>
                  <p>
                    Kept only in page memory and worker memory for this turn. Reloading clears it.
                  </p>
                  {byokInvalid ? (
                    <p role="alert">Enter at least 8 characters before starting a BYOK turn.</p>
                  ) : null}
                </div>
              ) : null}
            </fieldset>
            <div>
              <div className={styles.panelLabel}>Try one of these</div>
              <div className={styles.promptGrid} style={{ marginTop: 8 }}>
                {examplePrompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={styles.promptButton}
                    disabled={!state.sessionId || busy || gated || byokInvalid}
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
              The private runtime is ready. Use a prompt to start a real,
              ordered LunarForge turn. Network
              access remains denied unless a provider-enforced capability is available.
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
              {m.streaming ? <span className={styles.streamingCursor} aria-label="streaming" /> : null}
            </p>
          </div>
        ))}

        {state.errorMessage ? (
          <div className={styles.message} role="alert">
            <div className={styles.speaker}>LunarForge:</div>
            <p className={styles.agentText}>{state.errorMessage}</p>
          </div>
        ) : null}

        {visibleTools > 0 ? (
          <div className={styles.toolList}>
            {displayedTools.slice(0, visibleTools).map((tool) => (
              <div key={`${tool.time}-${tool.detail}`} className={styles.toolRow}>
                <span className={`${styles.toolKind} ${styles.kindRun}`}>tool</span>
                <span className={styles.toolName}>{tool.detail}</span>
                <span className={styles.toolArg}>structured event</span>
                <span className={styles.toolTime}>{tool.time}</span>
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
              <div className={styles.sheetTitle}>
                {currentApproval?.title ?? "Run command in sandbox"}
              </div>
              <div className={styles.sheetSub}>
                {currentApproval?.summary ?? "Runs validation. No network."}
              </div>
            </div>
            <span className={styles.sheetRisk}>
              {currentApproval?.risk ?? "medium"}
            </span>
          </div>
          <div className={styles.sheetCommand}>
            {currentApproval?.details ?? APPROVAL_COMMAND}
          </div>
          <div className={styles.sheetActions}>
            <Button ref={mobileDenyRef} variant="secondary" size="block" onClick={deny}>
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
            disabled={
              gated ||
              !state.sessionId ||
              phase === "offline" ||
              phase === "fatal" ||
              phase === "expired" ||
              phase === "limited"
            }
            placeholder={
              gated
                ? "Input paused while an approval is pending…"
                : phase === "provisioning"
                  ? "Provisioning the private sandbox…"
                  : phase === "offline"
                    ? "Reconnecting to the event stream…"
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
              <button
                type="button"
                className={styles.flag}
                onClick={() => void controller.compact()}
                disabled={busy || gated || !state.sessionId}
              >
                Compact context
              </button>
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
                disabled={
                  gated ||
                  busy ||
                  !state.sessionId ||
                  phase === "offline" ||
                  phase === "fatal" ||
                  phase === "expired" ||
                  phase === "limited" ||
                  byokInvalid ||
                  draft.trim().length === 0
                }
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
    <div
      className={`${styles.app} ${phase === "offline" ? styles.disconnected : ""}`}
      id="main"
    >
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
          <Button
            variant="outline"
            onClick={() => void controller.downloadProject()}
            disabled={!state.sandboxId || phase === "expired"}
          >
            Download project
          </Button>
          <Button
            variant="destructive"
            onClick={remove}
            disabled={!state.sandboxId}
          >
            Delete
          </Button>
          <LogoutButton />
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
          <div className={styles.mobileHeaderActions}>
            <Button variant="outline" size="sm" onClick={reset}>
              Reset
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={remove}
              disabled={!state.sandboxId}
            >
              Delete
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void controller.downloadProject()}
              disabled={!state.sandboxId || phase === "expired"}
            >
              Download
            </Button>
            <LogoutButton />
          </div>
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
                <span className={styles.segmentCount}> {state.changedPaths.length}</span>
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
        <div className={styles.mobilePanel} data-testid="mobile-panel">
          {segment === "Files" ? filesPanel : detailsPanel}
        </div>
      ) : null}
    </div>
  );
}
