/** Data for the /docs route. Mirrors `project/Docs.dc.html`. */

export type NavGroup = { title: string; items: NavItem[] };
export type NavItem = { label: string; href: string };

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

function group(title: string, items: string[]): NavGroup {
  return {
    title,
    items: items.map((label) => ({ label, href: `/docs/${slug(label)}` })),
  };
}

export const docsNav: NavGroup[] = [
  group("Getting started", [
    "Introduction",
    "Installation",
    "Quick start",
    "Configuration",
  ]),
  group("Using the agent", [
    "CLI usage",
    "Textual chat",
    "Projects and AGENTS.md",
    "File and project tools",
  ]),
  group("Execution", [
    "Permissions and approvals",
    "Local execution safety",
    "Docker mode",
    "Validation",
    "Browser validation",
  ]),
  group("Sessions", [
    "Sessions and resume",
    "Working-memory compaction",
    "Subagents",
  ]),
  group("Extending", ["MCP", "Plugins", "Git support"]),
  group("Reference", [
    "Event protocol",
    "Public Python API",
    "Troubleshooting",
    "Security model",
  ]),
];

export type OverviewSection = {
  title: string;
  items: { title: string; description: string; href: string }[];
};

function section(
  title: string,
  items: [string, string][],
): OverviewSection {
  return {
    title,
    items: items.map(([t, d]) => ({
      title: t,
      description: d,
      href: `/docs/${slug(t)}`,
    })),
  };
}

export const docsOverview: OverviewSection[] = [
  section("Getting started", [
    ["Introduction", "What LunarForge is and is not"],
    ["Installation", "pip, supported Python versions"],
    ["Quick start", "First task in five minutes"],
    ["Configuration", "lunarforge.yaml reference"],
    ["CLI usage", "Commands, flags, exit codes"],
    ["Textual chat", "Continuous terminal chat"],
  ]),
  section("Projects and safety", [
    ["Projects and AGENTS.md", "Root and nested instructions"],
    ["File and project tools", "Reads, writes, boundaries"],
    ["Permissions and approvals", "The approval gate"],
    ["Local execution safety", "What local mode does not isolate"],
    ["Docker mode", "Images, mounts, network"],
    ["Security model", "Threat model and guarantees"],
  ]),
  section("Validation and sessions", [
    ["Validation", "Running your check commands"],
    ["Browser validation", "Confirming rendered output"],
    ["Sessions and resume", "Persisting long tasks"],
    ["Working-memory compaction", "Keeping context usable"],
    ["Subagents", "Delegating focused work"],
    ["Git support", "Summaries and commits"],
  ]),
  section("Extending and reference", [
    ["MCP", "Attaching MCP servers"],
    ["Plugins", "Adding tools without forking"],
    ["Event protocol", "Every event type, versioned"],
    ["Public Python API", "Agent, Session, Approval"],
    ["Troubleshooting", "Common failures and fixes"],
    ["Changelog", "Milestones and releases"],
  ]),
];

/* ---- The "Permissions and approvals" article ---- */

export const approvalOptions: {
  option: string;
  type: string;
  fallback: string;
  description: string;
}[] = [
  [
    "approvals.default",
    "enum",
    "ask",
    "ask, allow, or deny for commands with no matching rule.",
  ],
  [
    "approvals.allow",
    "list[str]",
    "[]",
    "Glob patterns that bypass the gate for the current session.",
  ],
  [
    "approvals.deny",
    "list[str]",
    "[]",
    "Patterns refused outright; takes precedence over allow.",
  ],
  [
    "runtime",
    "enum",
    "local",
    "local or docker. Docker is recommended for untrusted work.",
  ],
  [
    "approvals.timeout",
    "int",
    "0",
    "Seconds before an unanswered request is denied. 0 waits indefinitely.",
  ],
].map(([option, type, fallback, description]) => ({
  option,
  type,
  fallback,
  description,
}));

export const approvalProcedure: string[] = [
  "Start a task with lunarforge run, or resume one with --session.",
  "When the gate opens, press v to inspect the full command, working directory, and runtime.",
  "Press a to approve or d to deny. The decision is recorded in the session transcript.",
];

export type TocEntry = { id: string; title: string; level: 0 | 1 };

export const approvalToc: TocEntry[] = [
  { id: "how-the-gate-works", title: "How the gate works", level: 0 },
  { id: "configuring-policy", title: "Configuring policy", level: 0 },
  { id: "options-reference", title: "Options reference", level: 0 },
  { id: "approving-from-the-cli", title: "Approving from the CLI", level: 0 },
  { id: "event-payload", title: "Event payload", level: 1 },
  { id: "resumed-sessions", title: "Resumed sessions", level: 1 },
];

/* ---- ⌘K search index ---- */

export type SearchKind = "page" | "event" | "api" | "go";

export type SearchResult = {
  kind: SearchKind;
  title: string;
  description: string;
  href: string;
};

export const searchIndex: SearchResult[] = [
  {
    kind: "page",
    title: "Permissions and approvals",
    description: "The approval gate, policy rules, and resumed sessions",
    href: "/docs/permissions-and-approvals",
  },
  {
    kind: "page",
    title: "Local execution safety",
    description: "Why local mode is a policy boundary, not an OS boundary",
    href: "/docs/local-execution-safety",
  },
  {
    kind: "event",
    title: "approval.requested",
    description: "Emitted when the agent needs a decision before executing",
    href: "/docs/event-protocol",
  },
  {
    kind: "api",
    title: "Approval.APPROVE",
    description: "Resolve a pending approval from the Python API",
    href: "/docs/public-python-api",
  },
  {
    kind: "page",
    title: "Docker mode",
    description: "Auto-approval patterns inside a container image",
    href: "/docs/docker-mode",
  },
  {
    kind: "page",
    title: "Quick start",
    description: "Install, run your first task in Docker, and approve a command",
    href: "/docs/quick-start",
  },
  {
    kind: "page",
    title: "Security model",
    description: "Threat model and the guarantees each runtime gives you",
    href: "/docs/security-model",
  },
  {
    kind: "page",
    title: "Sessions and resume",
    description: "Persisting long tasks and replaying pending approvals",
    href: "/docs/sessions-and-resume",
  },
  {
    kind: "event",
    title: "approval.resolved",
    description: "Carries the decision that unblocks a paused run",
    href: "/docs/event-protocol",
  },
  {
    kind: "api",
    title: "Agent.run",
    description: "Iterate the structured event stream for one task",
    href: "/docs/public-python-api",
  },
  {
    kind: "page",
    title: "Validation",
    description: "Running your check commands and reading the results",
    href: "/docs/validation",
  },
  {
    kind: "page",
    title: "Event protocol",
    description: "Every event type, versioned and JSON-safe",
    href: "/docs/event-protocol",
  },
];

/** Shown when the query is empty. */
export const recentPages: SearchResult[] = [
  searchIndex[0],
  searchIndex[5],
  searchIndex[4],
  searchIndex[11],
];

export const searchActions: SearchResult[] = [
  {
    kind: "go",
    title: "Open the sandbox",
    description: "Start a disposable browser session",
    href: "/sandbox",
  },
  {
    kind: "go",
    title: "Open the comparison",
    description: "One task, three coding agents",
    href: "/compare",
  },
];
