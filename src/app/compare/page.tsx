import type { Metadata } from "next";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteNav } from "@/components/SiteNav";
import { ButtonLink } from "@/components/ui/Button";
import {
  agents,
  caveats,
  diffCards,
  methodology,
  mobileRows,
  phases,
  qualitative,
  RUN_DATE,
  runRecord,
  taskFacts,
  timeBreakdown,
  tokenUsage,
} from "@/lib/compare";

import styles from "./compare.module.css";

export const metadata: Metadata = {
  title: "One task, three coding agents",
  description:
    "A single reproducible task run against LunarForge, Claude Code and Codex, with wall-clock time, token usage, cost, diff size and validation outcome recorded per run.",
};

const BADGE_CLASS = {
  accent: styles.badgeAccent,
  success: styles.badgeSuccess,
} as const;

export default function ComparePage() {
  return (
    <>
      <SiteNav />
      <main id="main" className={styles.page}>
        {/* ---------- Header ---------- */}
        <section className={styles.header}>
          <div className={styles.headerCopy}>
            <p className={styles.badge}>Benchmark · run {RUN_DATE}</p>
            <h1 className={styles.title}>
              The same task,
              <br />
              three coding agents.
            </h1>
            <p className={styles.lede}>
              One repository, one prompt, one validation command. We recorded
              wall-clock time, token usage, cost, the diff each agent produced
              and whether the test suite went green without human help.
              Everything below is reproducible from the run log.
            </p>
            <div className={styles.headerActions}>
              <ButtonLink href="#methodology" variant="primary" size="lg">
                Read the methodology
              </ButtonLink>
              <ButtonLink
                href="https://github.com/lunarforge/lunarforge"
                variant="outline"
                size="lg"
              >
                Download run log (JSON)
              </ButtonLink>
            </div>
          </div>

          <aside className={styles.taskCard}>
            <div className={styles.taskHead}>
              <span>The task</span>
              <span className={styles.taskHeadNote}>identical prompt</span>
            </div>
            <div className={styles.taskPrompt}>
              <div>Add cursor-based pagination to</div>
              <div>
                <span className={styles.taskEndpoint}>GET /api/threads</span>,
                keep the existing
              </div>
              <div>offset param working, and cover both</div>
              <div>paths with tests.</div>
            </div>
            <div className={styles.taskFacts}>
              {taskFacts.map((f) => (
                <div key={f.label} className={styles.taskFact}>
                  <div className={styles.factLabel}>{f.label}</div>
                  <div className={styles.factValue}>{f.value}</div>
                </div>
              ))}
            </div>
          </aside>
        </section>

        {/* ---------- Scoreboard ---------- */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2 className={styles.h2}>Results at a glance</h2>
            <span className={styles.sectionNote}>
              3 runs · 1 attempt each · no retries
            </span>
          </div>
          <div className={styles.scoreboard}>
            {agents.map((a) => (
              <article
                key={a.id}
                className={`${styles.agentCard} ${a.featured ? styles.agentFeatured : ""}`}
              >
                <div className={styles.agentHead}>
                  <h3 className={styles.agentName}>
                    <span
                      className={`${styles.agentMark} ${a.featured ? styles.agentMarkPrimary : ""}`}
                      aria-hidden="true"
                    >
                      {a.mark}
                    </span>
                    {a.name}
                  </h3>
                  <span
                    className={`${styles.agentBadge} ${BADGE_CLASS[a.badgeTone]}`}
                  >
                    {a.badge}
                  </span>
                </div>
                <div className={styles.metrics}>
                  <div className={styles.metric}>
                    <div className={styles.metricLabel}>Wall clock</div>
                    <div className={styles.metricBig}>{a.wallClock}</div>
                  </div>
                  <div className={styles.metric}>
                    <div className={styles.metricLabel}>Cost</div>
                    <div className={styles.metricBig}>{a.cost}</div>
                  </div>
                  <div className={styles.metric}>
                    <div className={styles.metricLabel}>Tokens</div>
                    <div className={styles.metricMid}>
                      {a.tokensIn} <span className={styles.metricUnit}>in</span>{" "}
                      · {a.tokensOut}{" "}
                      <span className={styles.metricUnit}>out</span>
                    </div>
                  </div>
                  <div className={styles.metric}>
                    <div className={styles.metricLabel}>Tests</div>
                    <div
                      className={`${styles.metricMid} ${a.testsTone === "success" ? styles.metricSuccess : styles.metricWarning}`}
                    >
                      {a.tests}
                    </div>
                  </div>
                </div>
                <p className={styles.agentNote}>{a.note}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- Time and tokens ---------- */}
        <section className={styles.section}>
          <div className={styles.breakdown}>
            <div className={styles.chartBlock}>
              <div>
                <h2 className={`${styles.h2} ${styles.h2Small}`}>
                  Where the time went
                </h2>
                <p className={styles.sectionIntro}>
                  Wall clock split by phase, measured from the event stream.
                  Approval waits are excluded — they depend on how fast a human
                  answers.
                </p>
              </div>

              <div className={styles.bars}>
                {timeBreakdown.map((row) => (
                  <div key={row.name} className={styles.barGroup}>
                    <div className={styles.barHead}>
                      <span className={styles.barName}>{row.name}</span>
                      <span className={styles.barTotal}>{row.total}</span>
                    </div>
                    <div
                      className={styles.barTrack}
                      style={{ width: row.width }}
                      role="img"
                      aria-label={`${row.name}: ${row.total} split across ${phases.map((p) => p.label).join(", ")}`}
                    >
                      {phases.map((p) => (
                        <span
                          key={p.key}
                          style={{
                            flex: row.parts[p.key],
                            background: p.color,
                          }}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              <div className={styles.legend}>
                {phases.map((p) => (
                  <span key={p.key} className={styles.legendItem}>
                    <span
                      className={styles.swatch}
                      style={{ background: p.color }}
                    />
                    {p.label}
                  </span>
                ))}
              </div>
            </div>

            <aside className={styles.tokenCard}>
              <div>
                <h3 className={styles.tokenTitle}>Token usage</h3>
                <p className={styles.tokenIntro}>
                  Input tokens dominate; context strategy is most of the cost
                  difference.
                </p>
              </div>
              <div className={styles.tokenRows}>
                {tokenUsage.map((t) => (
                  <div key={t.name} className={styles.tokenRow}>
                    <div className={styles.tokenHead}>
                      <span className={styles.tokenName}>{t.name}</span>
                      <span className={styles.tokenTotal}>{t.total}</span>
                    </div>
                    <div
                      className={styles.tokenTrack}
                      style={{ width: t.width }}
                      role="img"
                      aria-label={`${t.name}: ${t.total} total tokens`}
                    >
                      <span
                        style={{
                          flex: t.input,
                          background: t.highlight ? "#e8783a" : "#5a6169",
                        }}
                      />
                      <span
                        style={{
                          flex: t.output,
                          background: t.highlight ? "#8a4a22" : "#3a4046",
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className={styles.tokenLegend}>
                <span className={styles.tokenLegendItem}>
                  <span
                    className={styles.swatch}
                    style={{ background: "#5a6169" }}
                  />
                  Input
                </span>
                <span className={styles.tokenLegendItem}>
                  <span
                    className={styles.swatch}
                    style={{ background: "#3a4046" }}
                  />
                  Output
                </span>
              </div>
            </aside>
          </div>
        </section>

        {/* ---------- Full run record ---------- */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <h2 className={`${styles.h2} ${styles.h2Small}`}>Full run record</h2>
            <span className={styles.sectionNote}>
              every field taken from the event log
            </span>
          </div>

          <div className={styles.tableWrap}>
            <div className={styles.tableScroll}>
              <div className={styles.tableHead}>
                <div className={styles.thMeta}>Metric</div>
                <div className={`${styles.thAgent} ${styles.thPrimary}`}>
                  LunarForge
                </div>
                <div className={styles.thAgent}>Claude Code</div>
                <div className={styles.thAgent}>Codex</div>
                <div className={styles.thMeta}>Best</div>
              </div>
              {runRecord.map((r) => (
                <div key={r.metric} className={styles.tableRow}>
                  <div className={styles.tdMetric}>{r.metric}</div>
                  <div className={`${styles.tdValue} ${styles.tdPrimary}`}>
                    {r.lunarforge}
                  </div>
                  <div className={styles.tdValue}>{r.claudeCode}</div>
                  <div className={styles.tdValue}>{r.codex}</div>
                  <div className={styles.tdBest}>{r.best}</div>
                </div>
              ))}
            </div>
          </div>
          <p className={styles.tableNote}>
            “Best” is the better value for that row only. Rows where the
            difference is a design choice rather than a score are marked{" "}
            <span className={styles.tableNoteMono}>—</span>.
          </p>

          {/* Mobile: the same record, stacked. */}
          <div className={styles.mobileMetrics}>
            {mobileRows.map((r) => (
              <div key={r.metric} className={styles.mobileRow}>
                <div className={styles.mobileRowLabel}>{r.metric}</div>
                <div className={styles.mobileRowValues}>
                  <span className={styles.mobileValuePrimary}>
                    {r.values[0]}
                  </span>
                  <span className={styles.mobileValue}>{r.values[1]}</span>
                  <span className={styles.mobileValue}>{r.values[2]}</span>
                </div>
              </div>
            ))}
            <div className={styles.mobileLegend}>
              <span>LunarForge</span>
              <span>Claude Code</span>
              <span>Codex</span>
            </div>
          </div>
        </section>

        {/* ---------- Diffs ---------- */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <div>
              <h2 className={`${styles.h2} ${styles.h2Small}`}>
                What each agent actually produced
              </h2>
              <p className={styles.sectionIntro}>
                The numbers only go so far — the diff matters. Reviewed by the
                same engineer, blind to which agent wrote which patch.
              </p>
            </div>
          </div>
          <div className={styles.diffGrid}>
            {diffCards.map((d) => (
              <article key={d.name} className={styles.diffCard}>
                <div className={styles.diffHead}>
                  <h3 className={styles.diffName}>{d.name}</h3>
                  <span className={styles.diffStat}>{d.stat}</span>
                </div>
                <div className={styles.diffFiles}>
                  {d.files.map((f) => (
                    <div key={f.path} className={styles.diffFile}>
                      <span className={styles.diffPath}>{f.path}</span>
                      <span className={styles.diffDelta}>{f.delta}</span>
                    </div>
                  ))}
                </div>
                <p className={styles.diffNote}>{d.note}</p>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- Qualitative ---------- */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <div>
              <h2 className={`${styles.h2} ${styles.h2Small}`}>
                Differences the stopwatch doesn’t catch
              </h2>
              <p className={styles.sectionIntro}>
                Where the three tools genuinely diverge is not speed — it’s what
                they let happen without asking.
              </p>
            </div>
          </div>
          <div className={styles.qualGrid}>
            {qualitative.map((q) => (
              <article key={q.n} className={styles.qualCard}>
                <span className={styles.qualNum}>{q.n}</span>
                <div>
                  <h3 className={styles.qualTitle}>{q.title}</h3>
                  <p className={styles.qualBody}>{q.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* ---------- Methodology ---------- */}
        <section
          id="methodology"
          className={`${styles.section} ${styles.sunken}`}
        >
          <div className={styles.methodGrid}>
            <div className={styles.methodColumn}>
              <h2 className={styles.methodTitle}>Methodology</h2>
              <ul className={styles.methodList}>
                {methodology.map((m) => (
                  <li key={m} className={styles.methodItem}>
                    <span className={styles.markOk} aria-hidden="true">
                      ✓
                    </span>
                    {m}
                  </li>
                ))}
              </ul>
            </div>
            <div className={styles.methodColumn}>
              <h2 className={styles.methodTitle}>What this does not prove</h2>
              <ul className={styles.methodList}>
                {caveats.map((c) => (
                  <li key={c} className={styles.methodItem}>
                    <span className={styles.markWarn} aria-hidden="true">
                      !
                    </span>
                    {c}
                  </li>
                ))}
              </ul>
              <p className={styles.methodFoot}>
                One task is an anecdote, not a benchmark. The run log and the
                harness are in the repo — run it on your own repository before
                you believe any of it.
              </p>
            </div>
          </div>
        </section>

        {/* ---------- CTA ---------- */}
        <section className={`${styles.section} ${styles.cta}`}>
          <div>
            <h2 className={styles.ctaTitle}>Run it against your own repo</h2>
            <p className={styles.ctaBody}>
              The harness takes a prompt, a validation command and a Docker
              image, and writes the same table you just read.
            </p>
          </div>
          <div className={styles.ctaActions}>
            <ButtonLink href="/sandbox" variant="primary" size="lg">
              Try the sandbox
            </ButtonLink>
            <ButtonLink href="/docs" variant="outline" size="lg">
              Read the harness docs
            </ButtonLink>
          </div>
        </section>
      </main>
      <SiteFooter
        variant="compact"
        note={`Benchmark run ${RUN_DATE} · single attempt per agent · logs published unedited.`}
      />
    </>
  );
}
