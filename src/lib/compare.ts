/** Data for the /compare route. Mirrors `project/Comparison.dc.html`. */

export const RUN_DATE = "sample fixture";

export type Agent = {
  id: "lunarforge" | "claude-code" | "codex";
  name: string;
  mark: string;
  badge: string;
  badgeTone: "accent" | "success";
  featured: boolean;
  wallClock: string;
  cost: string;
  tokensIn: string;
  tokensOut: string;
  tests: string;
  testsTone: "success" | "warning";
  note: string;
};

export const agents: Agent[] = [
  {
    id: "lunarforge",
    name: "LunarForge",
    mark: "L",
    badge: "sample data",
    badgeTone: "accent",
    featured: true,
    wallClock: "6:12",
    cost: "$0.71",
    tokensIn: "128k",
    tokensOut: "9.4k",
    tests: "18 / 18 green",
    testsTone: "success",
    note: "Illustrative scenario: Docker execution, five approval gates, no hand edits, and no scope creep outside the touched modules.",
  },
  {
    id: "claude-code",
    name: "Claude Code",
    mark: "C",
    badge: "fastest",
    badgeTone: "success",
    featured: false,
    wallClock: "4:48",
    cost: "$0.83",
    tokensIn: "141k",
    tokensOut: "11.2k",
    tests: "18 / 18 green",
    testsTone: "success",
    note: "Illustrative scenario: host execution, a green suite, and one intervention for an unrelated serializer refactor.",
  },
  {
    id: "codex",
    name: "Codex",
    mark: "X",
    badge: "cheapest",
    badgeTone: "success",
    featured: false,
    wallClock: "7:35",
    cost: "$0.44",
    tokensIn: "96k",
    tokensOut: "8.1k",
    tests: "16 / 18",
    testsTone: "warning",
    note: "Illustrative scenario: container execution, the smallest diff, and two remaining failures on the legacy offset path.",
  },
];

/** Phase split of wall clock, measured from the event stream. */
export type PhaseKey = "inspect" | "plan" | "edit" | "validate" | "repair";

export const phases: { key: PhaseKey; label: string; color: string }[] = [
  { key: "inspect", label: "Inspect", color: "#3a4046" },
  { key: "plan", label: "Plan", color: "#4e565d" },
  { key: "edit", label: "Edit", color: "#e8783a" },
  { key: "validate", label: "Validate", color: "#5e9b72" },
  { key: "repair", label: "Repair", color: "#8e5a4e" },
];

export const timeBreakdown: {
  name: string;
  total: string;
  width: string;
  parts: Record<PhaseKey, number>;
}[] = [
  {
    name: "LunarForge",
    total: "6m 12s",
    width: "82%",
    parts: { inspect: 48, plan: 35, edit: 121, validate: 96, repair: 72 },
  },
  {
    name: "Claude Code",
    total: "4m 48s",
    width: "63%",
    parts: { inspect: 32, plan: 22, edit: 104, validate: 84, repair: 46 },
  },
  {
    name: "Codex",
    total: "7m 35s",
    width: "100%",
    parts: { inspect: 61, plan: 40, edit: 138, validate: 110, repair: 106 },
  },
];

export const tokenUsage: {
  name: string;
  total: string;
  width: string;
  input: number;
  output: number;
  highlight: boolean;
}[] = [
  {
    name: "LunarForge",
    total: "137.4k",
    width: "91%",
    input: 128,
    output: 9.4,
    highlight: true,
  },
  {
    name: "Claude Code",
    total: "152.2k",
    width: "100%",
    input: 141,
    output: 11.2,
    highlight: false,
  },
  {
    name: "Codex",
    total: "104.1k",
    width: "68%",
    input: 96,
    output: 8.1,
    highlight: false,
  },
];

export type RunRow = {
  metric: string;
  lunarforge: string;
  claudeCode: string;
  codex: string;
  best: string;
};

export const runRecord: RunRow[] = (
  [
    ["Wall clock", "6m 12s", "4m 48s", "7m 35s", "Claude Code"],
    ["Input tokens", "128.0k", "141.0k", "96.0k", "Codex"],
    ["Output tokens", "9.4k", "11.2k", "8.1k", "Codex"],
    ["Cost (same model pricing)", "$0.71", "$0.83", "$0.44", "Codex"],
    ["Tool calls", "34", "41", "28", "Codex"],
    ["Files changed", "4", "5", "3", "—"],
    ["Diff size", "+186 / −22", "+214 / −31", "+142 / −18", "—"],
    ["Tests after run", "18 / 18", "18 / 18", "16 / 18", "tie · LF, CC"],
    ["Human interventions", "0", "1", "2", "LunarForge"],
    ["Commands run unapproved", "0", "9 (allowlist)", "0", "tie · LF, CX"],
    ["Execution isolation", "Docker", "host", "container", "—"],
    ["Files touched outside scope", "0", "1", "0", "tie · LF, CX"],
    ["Resumable after restart", "yes", "partial", "no", "LunarForge"],
    [
      "Machine-readable run log",
      "JSON events",
      "transcript",
      "transcript",
      "LunarForge",
    ],
  ] as [string, string, string, string, string][]
).map(([metric, lunarforge, claudeCode, codex, best]) => ({
  metric,
  lunarforge,
  claudeCode,
  codex,
  best,
}));

export type DiffCard = {
  name: string;
  stat: string;
  files: { path: string; delta: string }[];
  note: string;
};

export const diffCards: DiffCard[] = [
  {
    name: "LunarForge",
    stat: "+186 / −22",
    note: "Kept the offset path intact behind a deprecation note, added an opaque cursor helper and tests for both paths. Reviewer had no comments.",
    files: [
      { path: "api/routes/threads.py", delta: "+64 −11" },
      { path: "api/pagination.py", delta: "+58 −0" },
      { path: "tests/test_threads.py", delta: "+51 −8" },
      { path: "docs/api.md", delta: "+13 −3" },
    ],
  },
  {
    name: "Claude Code",
    stat: "+214 / −31",
    note: "Correct and complete, but also rewrote an unrelated serializer for tidiness — reverted by hand before review.",
    files: [
      { path: "api/routes/threads.py", delta: "+71 −14" },
      { path: "api/pagination.py", delta: "+62 −0" },
      { path: "api/serializers.py", delta: "+22 −9" },
      { path: "tests/test_threads.py", delta: "+47 −5" },
      { path: "docs/api.md", delta: "+12 −3" },
    ],
  },
  {
    name: "Codex",
    stat: "+142 / −18",
    note: "Tightest patch of the three, but the cursor decoder rejected legacy offset requests, leaving two red tests it stopped short of fixing.",
    files: [
      { path: "api/routes/threads.py", delta: "+58 −13" },
      { path: "api/pagination.py", delta: "+49 −0" },
      { path: "tests/test_threads.py", delta: "+35 −5" },
    ],
  },
];

export const qualitative: { n: string; title: string; body: string }[] = (
  [
    [
      "01",
      "Approval boundaries",
      "A real run record should make approval settings explicit so wall-clock differences can be interpreted rather than treated as equivalent.",
    ],
    [
      "02",
      "Where the code runs",
      "A real comparison should distinguish host execution from container execution because the safety boundaries are materially different.",
    ],
    [
      "03",
      "Staying inside scope",
      "A useful review records out-of-scope edits even when they are technically sound.",
    ],
    [
      "04",
      "What you can replay",
      "LunarForge AgentEvent records are JSON-safe; any future harness should retain enough structured evidence to reproduce its calculations.",
    ],
  ] as [string, string, string][]
).map(([n, title, body]) => ({ n, title, body }));

export const methodology = [
  "Use the same repository commit and restore a clean checkout before each run.",
  "Use one verbatim prompt and record every follow-up intervention.",
  "Pin the same model and pricing basis before comparing token costs.",
  "Define wall-clock boundaries and approval-wait handling in advance.",
  "Fix the validation pass criterion before any agent starts.",
];

export const caveats = [
  "All values on this route are illustrative design fixtures, not measured benchmark results.",
  "No run log or benchmark harness is included in the current repository baseline.",
  "One task would not establish general performance even after a real run.",
  "Approval settings, runtime isolation, and provider accounting require explicit normalization.",
];

export const taskFacts: { label: string; value: string }[] = [
  { label: "Repository", value: "fictional fixture · 41k LOC" },
  { label: "Stack", value: "FastAPI · SQLAlchemy · pytest" },
  { label: "Model", value: "Same frontier model, all runs" },
  { label: "Pass criterion", value: "pytest -q green, no edits by hand" },
];

/** Compact metric rows used by the mobile layout. */
export const mobileRows: {
  metric: string;
  values: [string, string, string];
}[] = (
  [
    ["Human interventions", "0", "1", "2"],
    ["Unapproved commands", "0", "9", "0"],
    ["Isolation", "Docker", "host", "container"],
    ["Diff size", "+186", "+214", "+142"],
    ["Out-of-scope edits", "0", "1", "0"],
    ["Machine-readable log", "yes", "no", "no"],
  ] as [string, string, string, string][]
).map(([metric, a, b, c]) => ({ metric, values: [a, b, c] as [string, string, string] }));

export const mobileCards: {
  name: string;
  badge: string;
  time: string;
  cost: string;
  tokens: string;
  tests: string;
}[] = [
  {
    name: "LunarForge",
    badge: "this project",
    time: "6:12",
    cost: "$0.71",
    tokens: "137k",
    tests: "18 / 18 green",
  },
  {
    name: "Claude Code",
    badge: "fastest",
    time: "4:48",
    cost: "$0.83",
    tokens: "152k",
    tests: "18 / 18 green",
  },
  {
    name: "Codex",
    badge: "cheapest",
    time: "7:35",
    cost: "$0.44",
    tokens: "104k",
    tests: "16 / 18",
  },
];
