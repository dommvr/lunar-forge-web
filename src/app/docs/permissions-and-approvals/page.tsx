import type { Metadata } from "next";
import Link from "next/link";

import { DocsBar } from "@/components/docs/DocsBar";
import { DocsToc } from "@/components/docs/DocsToc";
import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import code from "@/components/ui/CodeBlock.module.css";
import { approvalOptions, approvalProcedure, approvalToc } from "@/lib/docs";

import styles from "../docs.module.css";

export const metadata: Metadata = {
  title: "Permissions and approvals",
  description:
    "The approval gate, how policies are configured, and how approvals behave in Docker mode and in resumed sessions.",
};

const YAML = `runtime: docker
approvals:
  default: ask
  allow:
    - "npm test"
    - "pytest -q"
  deny:
    - "curl *"       # network egress
    - "rm -rf *"`;

const SHELL = `$ lunarforge run "run validation and fix one failure" --runtime docker
  ⟩ approval required — run: pytest -q  (risk: low)
  ⟩ [a]pprove  [d]eny  [v]iew details
$ a
  ✓ 41 passed, 1 fixed · session 8f3c2a saved`;

const PAYLOAD = `{
  "type": "approval.requested",
  "id": "apr_7c1e",
  "action": "command.run",
  "summary": "pytest -q",
  "risk": "low",
  "runtime": "docker",
  "cwd": "/workspace/my-app"
}`;

function Heading({ id, children }: { id: string; children: string }) {
  return (
    <h2 id={id} className={styles.h2}>
      {children}
      <a className={styles.anchor} href={`#${id}`} aria-label={`Link to ${children}`}>
        #
      </a>
    </h2>
  );
}

export default function ApprovalsPage() {
  return (
    <>
      <DocsBar
        section="Execution"
        page="Permissions and approvals"
        toc={approvalToc}
      />
      <div className={styles.articleGrid}>
        <article className={styles.article}>
          <nav className={styles.breadcrumb} aria-label="Breadcrumb">
            <span>Execution</span>
            <span className={styles.breadcrumbSep}>/</span>
            <span className={styles.breadcrumbCurrent}>
              Permissions and approvals
            </span>
          </nav>

          <h1 className={styles.articleTitle}>Permissions and approvals</h1>
          <p className={styles.articleLede}>
            LunarForge never runs a command without a decision. This page
            describes the approval gate, how policies are configured, and how
            approvals behave in Docker mode and in resumed sessions.
          </p>

          <div className={styles.meta}>
            <span>Updated 2026-07-18</span>
            <span className={styles.metaSep}>·</span>
            <span>v0.8.2</span>
            <span className={styles.metaSep}>·</span>
            <a href="https://github.com/lunarforge/lunarforge">
              Edit this page on GitHub
            </a>
          </div>

          <div className={styles.body}>
            <section className={styles.block}>
              <Heading id="how-the-gate-works">How the gate works</Heading>
              <p className={styles.p}>
                When the agent needs to execute anything — a shell command, a
                Docker build, a browser check — it emits an{" "}
                <code className={styles.code}>approval.requested</code> event and
                blocks. The interface renders the request; nothing proceeds
                until it receives{" "}
                <code className={styles.code}>approval.resolved</code>.
              </p>
              <Callout kind="note">
                File edits inside the project directory do not require approval
                by default. Writes outside the project boundary are refused, not
                prompted.
              </Callout>
            </section>

            <section className={styles.block}>
              <Heading id="configuring-policy">Configuring policy</Heading>
              <p className={styles.p}>
                Approval policy lives in{" "}
                <code className={styles.code}>lunarforge.yaml</code> at the
                project root. Nested AGENTS.md files can tighten policy for a
                subtree, never loosen it.
              </p>

              <CodeBlock label="lunarforge.yaml" copyText={YAML}>
                <div>
                  <span className={code.key}>runtime</span>: docker
                </div>
                <div>
                  <span className={code.key}>approvals</span>:
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>default</span>: ask
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>allow</span>:
                </div>
                <div>
                  {"    "}- <span className={code.str}>&quot;npm test&quot;</span>
                </div>
                <div>
                  {"    "}- <span className={code.str}>&quot;pytest -q&quot;</span>
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>deny</span>:
                </div>
                <div>
                  {"    "}- <span className={code.str}>&quot;curl *&quot;</span>
                  {"       "}
                  <span className={code.dim}># network egress</span>
                </div>
                <div>
                  {"    "}- <span className={code.str}>&quot;rm -rf *&quot;</span>
                </div>
              </CodeBlock>

              <Callout kind="warning">
                An <code className={styles.code}>allow</code> entry skips the
                gate for every matching command in the session. Keep the list
                narrow and specific.
              </Callout>
            </section>

            <section className={styles.block}>
              <Heading id="options-reference">Options reference</Heading>
              <div className={styles.table}>
                <div className={styles.tableScroll}>
                  <div className={styles.tableHead}>
                    <div>Option</div>
                    <div>Type</div>
                    <div>Default</div>
                    <div>Description</div>
                  </div>
                  {approvalOptions.map((o) => (
                    <div key={o.option} className={styles.tableRow}>
                      <div className={styles.cellKey}>{o.option}</div>
                      <div className={styles.cellMono}>{o.type}</div>
                      <div className={styles.cellMono}>{o.fallback}</div>
                      <div className={styles.cellText}>{o.description}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className={styles.block}>
              <Heading id="approving-from-the-cli">
                Approving from the CLI
              </Heading>
              <ol className={styles.procedure}>
                {approvalProcedure.map((step, i) => (
                  <li key={step} className={styles.procedureStep}>
                    <span className={styles.procedureNum}>{i + 1}</span>
                    <span className={styles.procedureText}>{step}</span>
                  </li>
                ))}
              </ol>

              <CodeBlock tabs={["shell", "python", "json"]} copyText={SHELL}>
                <div>
                  <span className={code.ok}>$</span> lunarforge run{" "}
                  <span className={code.str}>
                    &quot;run validation and fix one failure&quot;
                  </span>{" "}
                  --runtime docker
                </div>
                <div className={code.dim}>
                  {"  "}⟩ approval required — run: pytest -q (risk: low)
                </div>
                <div className={code.dim}>
                  {"  "}⟩ [a]pprove [d]eny [v]iew details
                </div>
                <div>
                  <span className={code.ok}>$</span> a
                </div>
                <div className={code.dim}>
                  {"  "}✓ 41 passed, 1 fixed · session 8f3c2a saved
                </div>
              </CodeBlock>

              <h3 id="event-payload" className={styles.h2}>
                Event payload
              </h3>
              <CodeBlock
                label="approval.requested — event payload"
                copyText={PAYLOAD}
              >
                <div>{"{"}</div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;type&quot;</span>:{" "}
                  <span className={code.str}>&quot;approval.requested&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;id&quot;</span>:{" "}
                  <span className={code.str}>&quot;apr_7c1e&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;action&quot;</span>:{" "}
                  <span className={code.str}>&quot;command.run&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;summary&quot;</span>:{" "}
                  <span className={code.str}>&quot;pytest -q&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;risk&quot;</span>:{" "}
                  <span className={code.str}>&quot;low&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;runtime&quot;</span>:{" "}
                  <span className={code.str}>&quot;docker&quot;</span>,
                </div>
                <div>
                  {"  "}
                  <span className={code.key}>&quot;cwd&quot;</span>:{" "}
                  <span className={code.str}>
                    &quot;/workspace/my-app&quot;
                  </span>
                </div>
                <div>{"}"}</div>
              </CodeBlock>

              <Callout kind="danger">
                Auto-approving every command in local mode removes the only
                boundary between the agent and your machine. Use Docker mode
                instead of a blanket allow rule.
              </Callout>

              <h3 id="resumed-sessions" className={styles.h2}>
                Resumed sessions
              </h3>
              <Callout kind="tip">
                Resumed sessions replay pending approvals. If a task was stopped
                mid-gate, the request reappears with its original details
                intact.
              </Callout>
            </section>
          </div>

          <nav className={styles.pager} aria-label="Pagination">
            <Link
              href="/docs/file-and-project-tools"
              className={styles.pagerCard}
            >
              <div className={styles.pagerLabel}>← Previous</div>
              <div className={styles.pagerTitle}>File and project tools</div>
            </Link>
            <Link
              href="/docs/local-execution-safety"
              className={`${styles.pagerCard} ${styles.pagerNext}`}
            >
              <div className={styles.pagerLabel}>Next →</div>
              <div className={styles.pagerTitle}>Local execution safety</div>
            </Link>
          </nav>
        </article>

        <DocsToc entries={approvalToc} />
      </div>
    </>
  );
}
