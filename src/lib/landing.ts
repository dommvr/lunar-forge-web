/** Data for the / route. Mirrors `project/Landing.dc.html`. */

const pad2 = (i: number) => String(i + 1).padStart(2, "0");

export const trustPoints = [
  "Project-confined file tools",
  "Local or Docker execution",
  "Resumable continuous chat",
  "Structured events for multiple UIs",
];

export type Capability = { n: string; title: string; description: string };

export const capabilities: Capability[] = (
  [
    [
      "Inspect and understand projects",
      "Walks the tree, reads source, and follows root and nested AGENTS.md instructions before touching anything.",
    ],
    [
      "Plan and edit safely",
      "Proposes a plan, then applies scoped edits with file tools confined to the project directory.",
    ],
    [
      "Local and Docker execution",
      "Run approved commands on your machine or inside a container image you control.",
    ],
    [
      "Validation and browser checks",
      "Runs your validation commands and can drive a browser to confirm the change actually renders.",
    ],
    [
      "Textual continuous chat",
      "A terminal chat UI that keeps the conversation going across tasks instead of one-shot prompts.",
    ],
    [
      "Resumable sessions",
      "Sessions persist and compact working memory, so long tasks survive restarts.",
    ],
    [
      "Subagents",
      "Delegates focused work to specialist subagents and folds the results back into the main transcript.",
    ],
    [
      "MCP and plugins",
      "Attach MCP servers and plugins to extend the tool surface without forking the agent.",
    ],
    [
      "Structured event protocol",
      "Every step is a JSON-safe event — the same stream feeds the CLI, Textual, and web UIs.",
    ],
    [
      "Git-aware summaries",
      "Reads repository state, summarises what changed, and can prepare a commit for review.",
    ],
  ] as [string, string][]
).map(([title, description], i) => ({ n: pad2(i), title, description }));

export type SafetyMode = {
  title: string;
  badge: string;
  tone: "warning" | "success" | "neutral";
  description: string;
  rows: { k: string; v: string; tone: "success" | "error" | "muted" }[];
};

export const safetyModes: SafetyMode[] = [
  {
    title: "Local mode",
    badge: "convenient",
    tone: "warning",
    description:
      "Runs on your machine with your toolchain. File writes stay inside the project and every command waits for approval — but this is a policy boundary, not an OS boundary.",
    rows: [
      { k: "File writes", v: "project-confined", tone: "success" },
      { k: "Commands", v: "approval-gated", tone: "success" },
      { k: "OS isolation", v: "none", tone: "error" },
      { k: "Best for", v: "your own repos", tone: "muted" },
    ],
  },
  {
    title: "Docker mode",
    badge: "recommended",
    tone: "success",
    description:
      "The same agent, executing inside a container with a mounted project and a controlled image. The recommended path for untrusted code or unfamiliar dependencies.",
    rows: [
      { k: "File writes", v: "container + mount", tone: "success" },
      { k: "Commands", v: "approval-gated", tone: "success" },
      { k: "OS isolation", v: "container", tone: "success" },
      { k: "Best for", v: "untrusted work", tone: "muted" },
    ],
  },
  {
    title: "Hosted sandbox",
    badge: "UI preview",
    tone: "neutral",
    description:
      "The current browser route is a deterministic UI preview; it does not run LunarForge yet. The planned hosted runtime will use disposable, time-boxed E2B sandboxes.",
    rows: [
      { k: "File writes", v: "ephemeral", tone: "muted" },
      { k: "Commands", v: "approval-gated", tone: "success" },
      { k: "OS isolation", v: "remote", tone: "success" },
      { k: "Best for", v: "a first look", tone: "muted" },
    ],
  },
];

export type FlowStep = { n: string; title: string; description: string };

export const flowSteps: FlowStep[] = (
  [
    ["User request", "A task, in plain language"],
    ["LunarForge engine", "Inspect, plan, decide"],
    ["Structured events", "JSON-safe, UI-neutral"],
    ["Tools + approval gates", "Nothing runs unapproved"],
    ["Validation", "Commands and browser checks"],
    ["CLI · Textual · wrappers", "One transport-neutral contract"],
  ] as [string, string][]
).map(([title, description], i) => ({ n: pad2(i), title, description }));

export type WorkflowStep = {
  n: string;
  title: string;
  description: string;
  tag: string;
};

export const workflowSteps: WorkflowStep[] = (
  [
    [
      "Inspect repository",
      "Reads the tree, package manifests, and every AGENTS.md in scope.",
      "12 files",
    ],
    [
      "Plan changes",
      "Writes an explicit plan before editing, so you can redirect early.",
      "3 edits",
    ],
    [
      "Request approval",
      "Any command — local or Docker — pauses for an explicit decision.",
      "1 gate",
    ],
    [
      "Edit files",
      "Scoped writes inside the project; nothing outside the boundary.",
      "3 files",
    ],
    [
      "Run validation",
      "Your validation commands, plus optional browser checks.",
      "passed",
    ],
    [
      "Review and commit",
      "A Git-aware summary you can edit, then commit on your terms.",
      "staged",
    ],
  ] as [string, string, string][]
).map(([title, description, tag], i) => ({
  n: String(i + 1),
  title,
  description,
  tag,
}));

export type DevPoint = { n: string; title: string; description: string };

export const devPoints: DevPoint[] = (
  [
    [
      "Python package",
      "Install the lunar-forge distribution. Import lunar_forge, then drive its typed event API from scripts and CI.",
    ],
    [
      "Provider-neutral model layer",
      "Swap model providers without rewriting prompts, tools, or session handling.",
    ],
    [
      "JSON-safe event protocol",
      "Every event serialises cleanly — log it, replay it, or render it in your own UI.",
    ],
    [
      "Public package API",
      "A documented surface for agents, sessions, tools, and approvals.",
    ],
    [
      "Web and cloud ready",
      "The event stream is transport-agnostic, so a hosted or web frontend is a client, not a fork.",
    ],
  ] as [string, string][]
).map(([title, description], i) => ({ n: pad2(i), title, description }));

export const footerColumns: { title: string; items: NavLink[] }[] = [
  {
    title: "Product",
    items: [
      { label: "Docs", href: "/docs" },
      { label: "Sandbox", href: "/sandbox" },
      { label: "Quick start", href: "/docs/quick-start" },
    ],
  },
  {
    title: "Source",
    items: [
      { label: "GitHub", href: "https://github.com/dommvr/lunar-forge" },
      { label: "Introduction", href: "/docs/introduction" },
      { label: "Security", href: "/docs/security-model" },
    ],
  },
  {
    title: "Reference",
    items: [
      { label: "Event protocol", href: "/docs/event-protocol" },
      { label: "Python API", href: "/docs/public-python-api" },
      { label: "Troubleshooting", href: "/docs/troubleshooting" },
    ],
  },
];

export type NavLink = { label: string; href: string };

export const RELEASE = "v0.1.0 · stable core API — hosted integration in progress";
export const RELEASE_SHORT = "v0.1.0 · core API";
