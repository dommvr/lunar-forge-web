import { CapabilityGrid } from "@/components/CapabilityGrid";
import { EmberField } from "@/components/EmberField";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { ButtonLink } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import code from "@/components/ui/CodeBlock.module.css";
import {
  capabilities,
  devPoints,
  flowSteps,
  safetyModes,
  trustPoints,
  workflowSteps,
} from "@/lib/landing";

import styles from "./page.module.css";

const BADGE_CLASS = {
  warning: styles.badgeWarning,
  success: styles.badgeSuccess,
  neutral: styles.badgeNeutral,
} as const;

const TONE_CLASS = {
  success: styles.toneSuccess,
  error: styles.toneError,
  muted: styles.toneMuted,
} as const;

const PYTHON_SNIPPET = `# From a LunarForge checkout: python -m pip install -e .
from lunar_forge import AgentRequest, run_agent_events

request = AgentRequest(
    project_root="./my-app",
    message="Run validation and fix one failure",
    runtime_mode="docker",
    reasoning_effort="high",
)

for event in run_agent_events(request):
    print(event.to_json())  # bounded, redacted, JSON-safe`;

export default function LandingPage() {
  return (
    <>
      <EmberField />
      <SiteNav />
      <main id="main" className={styles.page}>
        {/* ---------- Hero ---------- */}
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <p className={styles.pill}>
              <span className={styles.dotGreen} aria-hidden="true" />
              v0.1.0 · stable core API — hosted integration in progress
            </p>
            <h1 className={styles.h1}>
              A safe, extensible coding agent for real projects.
            </h1>
            <p className={styles.lede}>
              LunarForge inspects your repository, follows root and nested
              AGENTS.md instructions, plans changes, edits files inside project
              boundaries, and runs only the commands you approve — locally or in
              Docker.
            </p>
            <div className={styles.heroActions}>
              <ButtonLink href="/sandbox" variant="primary" size="hero">
                Try the sandbox
              </ButtonLink>
              <ButtonLink href="/docs" variant="quiet" size="hero">
                Read the docs
              </ButtonLink>
            </div>
            <ul className={styles.trust}>
              {trustPoints.map((t) => (
                <li key={t} className={styles.trustItem}>
                  <span className={styles.trustDot} aria-hidden="true" />
                  {t}
                </li>
              ))}
            </ul>
          </div>

          <figure className={styles.transcript}>
            <figcaption className={styles.transcriptHead}>
              <span className={styles.session}>
                <span className={styles.dotGreen} aria-hidden="true" />
                lunar-forge · session 8f3c2a
              </span>
              <span className={styles.tags}>
                <span className={styles.tag}>docker</span>
                <span className={styles.tag}>effort: high</span>
              </span>
            </figcaption>
            <div className={styles.transcriptBody}>
              <div>
                <div className={styles.speaker}>You:</div>
                <div className={styles.said}>
                  Add a responsive pricing section to the marketing site.
                </div>
              </div>

              <div className={styles.turn}>
                <div className={styles.speaker}>LunarForge:</div>
                <div className={styles.progress}>
                  Inspecting project · 12 files matched · reading AGENTS.md
                </div>
                <div className={styles.toolRow}>
                  <span className={styles.toolKind}>tool</span>
                  <span className={styles.toolName}>read_file</span>
                  <span className={styles.toolArg}>
                    src/app/(marketing)/page.tsx
                  </span>
                  <span className={styles.toolTime}>0.4s</span>
                </div>
                <div className={styles.toolRow}>
                  <span className={styles.toolKind}>tool</span>
                  <span className={styles.toolName}>edit_file</span>
                  <span className={styles.toolArg}>3 edits · 1 new file</span>
                  <span className={styles.toolTime}>1.2s</span>
                </div>
              </div>

              <div className={styles.approval}>
                <div className={styles.approvalHead}>
                  <span className={styles.approvalTitle}>Approval required</span>
                  <span className={styles.riskChip}>risk: medium</span>
                </div>
                <div className={styles.approvalBody}>
                  <div className={styles.approvalCmd}>
                    run <span className={styles.said}>npm run build</span>
                  </div>
                  <div className={styles.approvalMeta}>
                    docker · project-confined · no network
                  </div>
                  <div className={styles.approvalActions}>
                    <ButtonLink href="/sandbox" variant="secondary" size="sm">
                      Deny
                    </ButtonLink>
                    <ButtonLink href="/sandbox" variant="primary" size="sm">
                      Approve
                    </ButtonLink>
                  </div>
                </div>
              </div>

              <div>
                <div className={styles.speaker}>LunarForge:</div>
                <div className={styles.said}>
                  Edited 3 files. Build and validation passed in 41s.
                </div>
                <div className={styles.summary}>
                  Staged summary — feat(marketing): responsive pricing section
                </div>
              </div>
            </div>
          </figure>
        </section>

        {/* ---------- Capabilities ---------- */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <div className={styles.sectionHeadCopy}>
              <p className={styles.eyebrow}>Capabilities</p>
              <h2 className={styles.h2}>
                Everything the agent does, in the open.
              </h2>
            </div>
            <p className={styles.sectionAside}>
              Core activity emits structured events, so the CLI, Textual chat,
              and future web integration can render the same public contract.
            </p>
          </div>
          <CapabilityGrid items={capabilities} />
        </section>

        {/* ---------- Safety model ---------- */}
        <section className={`${styles.section} ${styles.sunken}`}>
          <div className={styles.stack}>
            <p className={styles.eyebrow}>Safety model</p>
            <h2 className={styles.h2}>
              Convenience and isolation are not the same thing.
            </h2>
            <p className={styles.lede2}>
              Local mode keeps file writes inside the project and gates every
              command behind approval — but it is not OS-level isolation. Run
              untrusted work in Docker.
            </p>
          </div>
          <div className={styles.modeGrid}>
            {safetyModes.map((m) => (
              <article key={m.title} className={styles.mode}>
                <div className={styles.modeHead}>
                  <h3 className={styles.modeTitle}>{m.title}</h3>
                  <span
                    className={`${styles.modeBadge} ${BADGE_CLASS[m.tone]}`}
                  >
                    {m.badge}
                  </span>
                </div>
                <div className={styles.modeBody}>
                  <p className={styles.modeText}>{m.description}</p>
                  <dl className={styles.modeRows}>
                    {m.rows.map((r) => (
                      <div key={r.k} className={styles.modeRow}>
                        <dt className={styles.modeRowKey}>{r.k}</dt>
                        <dd
                          className={`${styles.modeRowValue} ${TONE_CLASS[r.tone]}`}
                        >
                          {r.v}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- How it works ---------- */}
        <section className={styles.section}>
          <div className={styles.stack}>
            <p className={styles.eyebrow}>How it works</p>
              <h2 className={styles.h2}>
                One engine, one event stream, multiple interfaces.
              </h2>
          </div>
          <ol className={styles.flow}>
            {flowSteps.map((f, i) => (
              <li key={f.n} className={styles.flowItem}>
                <div className={styles.flowCard}>
                  <div className={styles.flowIndex}>{f.n}</div>
                  <div className={styles.flowTitle}>{f.title}</div>
                  <div className={styles.flowBody}>{f.description}</div>
                </div>
                {i < flowSteps.length - 1 ? (
                  <span className={styles.flowArrow} aria-hidden="true">
                    →
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </section>

        {/* ---------- Example workflow ---------- */}
        <section className={`${styles.section} ${styles.sunken}`}>
          <div className={styles.split}>
            <div className={styles.stack}>
              <p className={styles.eyebrow}>Example workflow</p>
              <h2 className={styles.h2}>A typical task, start to commit.</h2>
              <p className={styles.lede2} style={{ maxWidth: 420 }}>
                Every step is visible in the transcript and resumable. Stop at
                any point; the session picks up where it left off.
              </p>
            </div>
            <ol className={styles.steps}>
              {workflowSteps.map((s) => (
                <li key={s.n} className={styles.step}>
                  <span className={styles.stepIndex}>{s.n}</span>
                  <span className={styles.stepCopy}>
                    <span className={styles.stepTitle}>{s.title}</span>
                    <span className={styles.stepBody}>{s.description}</span>
                  </span>
                  <span className={styles.stepTag}>{s.tag}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---------- For developers ---------- */}
        <section className={styles.section}>
          <div className={`${styles.split} ${styles.splitEven}`}>
            <div className={styles.stack}>
              <p className={styles.eyebrow}>For developers</p>
              <h2 className={styles.h2}>A Python package, not a black box.</h2>
              <div className={styles.devList}>
                {devPoints.map((d) => (
                  <div key={d.n} className={styles.devItem}>
                    <span className={styles.devIndex}>{d.n}</span>
                    <span className={styles.stepCopy}>
                      <span className={styles.devTitle}>{d.title}</span>
                      <span className={styles.devBody}>{d.description}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <CodeBlock label="python" copyText={PYTHON_SNIPPET} density="roomy">
                <div className={code.dim}>
                  # From a LunarForge checkout: python -m pip install -e .
                </div>
                <div>
                  <span className={code.kw}>from</span> lunar_forge{" "}
                  <span className={code.kw}>import</span> AgentRequest,
                  run_agent_events
                </div>
                <div>&nbsp;</div>
                <div>request = AgentRequest(</div>
                <div>
                  {"    "}project_root=
                  <span className={code.str}>&quot;./my-app&quot;</span>,
                </div>
                <div>
                  {"    "}message=
                  <span className={code.str}>
                    &quot;Run validation and fix one failure&quot;
                  </span>
                  ,
                </div>
                <div>
                  {"    "}runtime_mode=
                  <span className={code.str}>&quot;docker&quot;</span>,
                </div>
                <div>
                  {"    "}reasoning_effort=
                  <span className={code.str}>&quot;high&quot;</span>,
                </div>
                <div>)</div>
                <div>&nbsp;</div>
                <div>
                  <span className={code.kw}>for</span> event{" "}
                  <span className={code.kw}>in</span> run_agent_events(request):
                </div>
                <div>
                  {"    "}print(event.to_json()){"  "}
                  <span className={code.dim}>
                    # bounded, redacted, JSON-safe
                  </span>
                </div>
              </CodeBlock>
            </div>
          </div>
        </section>

        {/* ---------- Final CTA ---------- */}
        <section className={`${styles.section} ${styles.sunken} ${styles.cta}`}>
          <h2 className={styles.ctaTitle}>
            Point it at a repository. Approve the first command.
          </h2>
          <p className={styles.ctaBody}>
            The browser route currently replays a deterministic UI fixture. The
            hosted runtime will connect this preserved interface to the same
            structured core events.
          </p>
          <div className={styles.ctaActions}>
            <ButtonLink href="/sandbox" variant="primary" size="cta">
              Try the sandbox
            </ButtonLink>
            <ButtonLink href="/docs" variant="quiet" size="cta">
              Read the docs
            </ButtonLink>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
