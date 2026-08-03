/** Data and state model for the /sandbox route. Mirrors `project/Sandbox.dc.html`. */

export type FileNode = {
  icon: "▾" | "·";
  name: string;
  level: number;
  tag: "" | "A" | "M";
};

export function projectTree(changed: boolean): FileNode[] {
  return (
    [
      ["▾", "sample-app", 0, ""],
      ["▾", "app", 1, ""],
      ["·", "layout.tsx", 2, ""],
      ["·", "page.tsx", 2, changed ? "M" : ""],
      ["▾", "components", 1, ""],
      ["·", "Hero.tsx", 2, ""],
      ["·", "Pricing.tsx", 2, changed ? "A" : ""],
      ["·", "Nav.tsx", 2, ""],
      ["·", "AGENTS.md", 1, ""],
      ["·", "package.json", 1, changed ? "M" : ""],
      ["·", ".agent/config.yaml", 1, ""],
      ["·", "README.md", 1, ""],
    ] as [FileNode["icon"], string, number, FileNode["tag"]][]
  ).map(([icon, name, level, tag]) => ({ icon, name, level, tag }));
}

export const panelTabs = [
  "Activity",
  "Validation",
  "Artifacts",
  "Usage",
] as const;
export type PanelTab = (typeof panelTabs)[number];

export const examplePrompts = [
  "Explain this project",
  "Add a responsive pricing section",
  "Run validation and fix one failure",
  "Review the project without editing files",
];

export type MetaChip = { k: string; v: string; hot?: boolean };

export const readyMeta: MetaChip[] = [
  { k: "session", v: "fixture" },
  { k: "runtime", v: "scripted" },
  { k: "model", v: "not connected" },
  { k: "effort", v: "n/a" },
  { k: "network", v: "not connected" },
  { k: "time left", v: "preview" },
];

export const activeMeta: MetaChip[] = [
  { k: "session", v: "fixture" },
  { k: "runtime", v: "scripted" },
  { k: "model", v: "not connected" },
  { k: "effort", v: "n/a" },
  { k: "network", v: "not connected" },
  { k: "time left", v: "preview", hot: true },
];

export type ActivityEvent = {
  name: string;
  detail: string;
  time: string;
  tone: "success" | "muted";
};

export const activityLog: ActivityEvent[] = [
  {
    name: "session.started",
    detail: "deterministic UI fixture",
    time: "0.0s",
    tone: "success",
  },
  {
    name: "status.updated",
    detail: "sample project fixture loaded",
    time: "0.4s",
    tone: "success",
  },
  {
    name: "tool.started",
    detail: "read_file · AGENTS.md",
    time: "0.6s",
    tone: "success",
  },
  {
    name: "tool.finished",
    detail: "read_file · ok",
    time: "0.7s",
    tone: "muted",
  },
  {
    name: "status.updated",
    detail: "fixture ready · no backend attached",
    time: "0.8s",
    tone: "muted",
  },
];

export type ToolRow = {
  kind: "read" | "edit" | "run";
  name: string;
  arg: string;
  time: string;
};

export const toolRows: ToolRow[] = [
  { kind: "read", name: "AGENTS.md", arg: "root + app/", time: "0.3s" },
  { kind: "read", name: "app/page.tsx", arg: "142 lines", time: "0.4s" },
  {
    kind: "edit",
    name: "components/Pricing.tsx",
    arg: "new file · 86 lines",
    time: "1.2s",
  },
  {
    kind: "run",
    name: "npm run validate",
    arg: "awaiting approval",
    time: "—",
  },
];

export const APPROVAL_COMMAND =
  "npm run validate -- --reporter=json --max-warnings=0 --project /workspace/sample-app --output /workspace/.agent/validation-8f3c2a.json";

export const approvalMeta: { k: string; v: string }[] = [
  { k: "runtime", v: "docker · node-22 · no network" },
  { k: "cwd", v: "/workspace/sample-app" },
  { k: "writes", v: ".agent/ (session artifacts)" },
  { k: "requested by", v: "main agent · step 4 of 5" },
];

export type ValidationStep = {
  icon: "✓" | "•";
  name: string;
  detail: string;
  tone: "success" | "warning" | "faint";
};

export const validationSteps: ValidationStep[] = [
  { icon: "✓", name: "typecheck", detail: "1.8s", tone: "success" },
  { icon: "✓", name: "lint", detail: "2.4s", tone: "success" },
  { icon: "✓", name: "unit tests", detail: "41 passed", tone: "success" },
  { icon: "•", name: "build", detail: "queued", tone: "warning" },
  { icon: "•", name: "browser check", detail: "queued", tone: "faint" },
];

export const usageRows = [
  { k: "Session time", v: "18:24 left" },
  { k: "Commands run", v: "3 of 20" },
  { k: "Events emitted", v: "148" },
];

export const PRICING_PREVIEW = [
  "+ export function Pricing() {",
  "+   return (",
  '+     <section className="pricing">',
  "+       {tiers.map((t) => (",
  "+         <Tier key={t.id} {...t} />",
  "+       ))}",
  "+     </section>",
  "+   );",
  "+ }",
];

/* ---- The full state matrix ---- */

export type StateTone = "muted" | "warning" | "success" | "accent" | "error";

export type SandboxState = {
  title: string;
  key: string;
  tone: StateTone;
  line: string;
  body: string;
  actions: { label: string; kind: "primary" | "secondary" | "destructive" }[];
  progress?: string;
};

const KIND = { p: "primary", s: "secondary", d: "destructive" } as const;

export const sandboxStates: SandboxState[] = (
  [
    [
      "No sandbox yet",
      "idle",
      "muted",
      "No session",
      "Start a sandbox to try LunarForge. Sessions are disposable and time-boxed to 30 minutes.",
      ["Start sandbox|p", "View docs|s"],
    ],
    [
      "Provisioning",
      "booting",
      "warning",
      "Provisioning container…",
      "Pulling the image and mounting the sample project. Usually under five seconds.",
      ["Cancel|s"],
      "38%",
    ],
    [
      "Ready",
      "ready",
      "success",
      "Sandbox ready · 29:41 left",
      "Sample project loaded at /workspace/sample-app. Ask a question or pick an example prompt.",
      ["Explain this project|p", "Reset|s"],
    ],
    [
      "Agent working",
      "running",
      "accent",
      "Editing files · 00:22",
      "Public progress lines stream in; the input stays open for follow-ups but queues them.",
      ["Stop task|d", "Compact context|s"],
      "62%",
    ],
    [
      "Waiting for approval",
      "gated",
      "warning",
      "Approval required · run npm run validate",
      "Everything pauses. Deny and Approve stay pinned above the input on every viewport.",
      ["Deny|s", "Approve|p"],
    ],
    [
      "Validation running",
      "validating",
      "accent",
      "Running validation · step 4 of 5",
      "Live output goes to the Validation tab; the transcript keeps a single summary line.",
      ["Stop task|d", "Open Validation|s"],
      "80%",
    ],
    [
      "Task completed",
      "done",
      "success",
      "Done · 3 files changed · 41s",
      "Summary, changed-file list, and an offer to prepare a commit message for review.",
      ["Review changes|p", "New task|s"],
    ],
    [
      "Cancelled + rollback",
      "cancelled",
      "muted",
      "Task stopped · edits rolled back",
      "Stop reverts uncommitted edits from this task and reports exactly what was undone.",
      ["Undo rollback|s", "New task|s"],
    ],
    [
      "Sandbox expired",
      "expired",
      "muted",
      "Session expired after 30:00",
      "The container was destroyed. The transcript stays readable; start a fresh sandbox to continue.",
      ["Start new sandbox|p", "Copy transcript|s"],
    ],
    [
      "Rate limited",
      "limited",
      "warning",
      "Hourly limit reached",
      "You have used 5 of 5 sandbox sessions this hour. Local install has no limit.",
      ["Install locally|p", "Retry in 12:04|s"],
    ],
    [
      "Backend disconnected",
      "offline",
      "warning",
      "Reconnecting… attempt 2 of 5",
      "The event stream dropped. Panels dim and hold their last state; the session is preserved server-side.",
      ["Reconnect now|s"],
      "45%",
    ],
    [
      "Recoverable error",
      "error",
      "error",
      "Command failed with exit code 1",
      "The agent shows the failing output and proposes a next step. Nothing else was changed.",
      ["Let it fix this|p", "View output|s"],
    ],
    [
      "Fatal sandbox error",
      "fatal",
      "error",
      "Sandbox terminated unexpectedly",
      "The container could not be recovered. Report the session ID so we can trace it.",
      ["Start new sandbox|p", "Copy session ID|s"],
    ],
  ] as [
    string,
    string,
    StateTone,
    string,
    string,
    string[],
    string | undefined,
  ][]
).map(([title, key, tone, line, body, actions, progress]) => ({
  title,
  key,
  tone,
  line,
  body,
  progress,
  actions: actions.map((a) => {
    const [label, kind] = a.split("|") as [string, keyof typeof KIND];
    return { label, kind: KIND[kind] };
  }),
}));
