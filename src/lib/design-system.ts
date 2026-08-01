/** Data for the /design-system reference route. Mirrors `project/Design System.dc.html`. */

export type Token = { name: string; value: string };
export type TokenGroup = { title: string; items: Token[] };

export const colorGroups: TokenGroup[] = (
  [
    [
      "Surfaces",
      [
        ["--bg", "#0B0C0D"],
        ["--surface-1", "#101214"],
        ["--surface-2", "#131518"],
        ["--surface-3", "#191C1F"],
        ["--surface-nav", "#0E1012"],
        ["--surface-sunken", "#0D0F10"],
      ],
    ],
    [
      "Borders and text",
      [
        ["--border", "#24272B"],
        ["--border-subtle", "#1D2023"],
        ["--border-strong", "#2C3035"],
        ["--text", "#E7E9EA"],
        ["--text-muted", "#8E959B"],
        ["--text-faint", "#5E656B"],
      ],
    ],
    [
      "Accents",
      [
        ["--accent", "#E8783A"],
        ["--accent-hover", "#F0925C"],
        ["--accent-press", "#C9581F"],
        ["--accent-ink", "#180D05"],
        ["--amber", "#E5A33B"],
        ["--accent-ring", "#3A2C1C"],
      ],
    ],
    [
      "Semantic",
      [
        ["--success", "#5E9B72"],
        ["--success-bg", "#0F1412"],
        ["--warning", "#E5A33B"],
        ["--warning-bg", "#141210"],
        ["--error", "#C4655C"],
        ["--error-bg", "#141011"],
      ],
    ],
  ] as [string, [string, string][]][]
).map(([title, items]) => ({
  title,
  items: items.map(([name, value]) => ({ name, value })),
}));

const SANS = "var(--font-sans)";
const MONO = "var(--font-mono)";

export type TypeRow = {
  name: string;
  spec: string;
  size: string;
  weight: number;
  tracking: string;
  family: string;
  sample: string;
};

export const typeScale: TypeRow[] = (
  [
    [
      "display",
      "56 / 1.06 / 600",
      "56px",
      600,
      "-0.028em",
      SANS,
      "A safe, extensible coding agent",
    ],
    [
      "h1",
      "38 / 1.15 / 600",
      "38px",
      600,
      "-0.025em",
      SANS,
      "Permissions and approvals",
    ],
    ["h2", "24 / 1.3 / 600", "24px", 600, "-0.015em", SANS, "How the gate works"],
    ["h3", "18 / 1.4 / 600", "18px", 600, "-0.01em", SANS, "Configuring policy"],
    [
      "body-lg",
      "17 / 1.7 / 400",
      "17px",
      400,
      "0",
      SANS,
      "Prose in documentation articles",
    ],
    [
      "body",
      "15 / 1.65 / 400",
      "15px",
      400,
      "0",
      SANS,
      "Interface copy and chat messages",
    ],
    ["ui", "13.5 / 1.4 / 500", "13.5px", 500, "0", SANS, "Buttons, tabs, controls"],
    [
      "mono",
      "13 / 1.7 / 400",
      "13px",
      400,
      "0",
      MONO,
      "npm run validate --reporter=json",
    ],
    ["eyebrow", "11 / 0.1em / mono", "11px", 500, "0.1em", MONO, "ON THIS PAGE"],
  ] as [string, string, string, number, string, string, string][]
).map(([name, spec, size, weight, tracking, family, sample]) => ({
  name,
  spec,
  size,
  weight,
  tracking,
  family,
  sample,
}));

export const spacingScale: Token[] = (
  [
    ["space-1", "4px"],
    ["space-2", "8px"],
    ["space-3", "16px"],
    ["space-4", "24px"],
    ["space-5", "32px"],
    ["space-6", "40px"],
    ["space-7", "56px"],
    ["space-8", "80px"],
  ] as [string, string][]
).map(([name, value]) => ({ name, value }));

export const radiusScale: Token[] = (
  [
    ["r-xs", "4px"],
    ["r-sm", "6px"],
    ["r-md", "8px"],
    ["r-lg", "10px"],
    ["r-full", "999px"],
  ] as [string, string][]
).map(([name, value]) => ({ name, value }));

export const elevationRules: { name: string; description: string }[] = (
  [
    [
      "flat",
      "Page and sidebar surfaces. Separation by 1px border only, never a shadow.",
    ],
    ["raised", "Cards and code blocks: surface-1 with --border. No shadow at rest."],
    [
      "overlay",
      "Dialogs, command menu, mobile sheets: 0 30px 60px -35px #000 plus --border-strong.",
    ],
    [
      "focus",
      "2px --accent ring offset 2px from the page background, on every interactive element.",
    ],
  ] as [string, string][]
).map(([name, description]) => ({ name, description }));

export type StatusBadge = {
  label: string;
  color: string;
  bg: string;
  ring: string;
};

export const statusBadges: StatusBadge[] = (
  [
    ["Ready", "#5E9B72", "#0F1412", "#1C2A20"],
    ["Working", "#E8783A", "#141210", "#3A2C1C"],
    ["Waiting", "#E5A33B", "#141210", "#3A2C1C"],
    ["Expired", "#8E959B", "#0F1113", "#24272B"],
    ["Error", "#C4655C", "#141011", "#4A2E2C"],
    ["Offline", "#8E959B", "#0F1113", "#24272B"],
  ] as [string, string, string, string][]
).map(([label, color, bg, ring]) => ({ label, color, bg, ring }));

export type FileRow = {
  icon: string;
  name: string;
  tag: string;
  tagColor: string;
  selected: boolean;
  dim: boolean;
};

export const fileRows: FileRow[] = [
  { icon: "▾", name: "components", tag: "", tagColor: "", selected: false, dim: false },
  { icon: "·", name: "Hero.tsx", tag: "", tagColor: "", selected: false, dim: true },
  {
    icon: "·",
    name: "Pricing.tsx",
    tag: "A",
    tagColor: "var(--success)",
    selected: true,
    dim: false,
  },
  {
    icon: "·",
    name: "page.tsx",
    tag: "M",
    tagColor: "var(--amber)",
    selected: false,
    dim: true,
  },
  {
    icon: "·",
    name: "AGENTS.md",
    tag: "ro",
    tagColor: "var(--text-faint)",
    selected: false,
    dim: true,
  },
];

export const calloutSamples: {
  kind: "note" | "tip" | "warning" | "danger";
  body: string;
}[] = [
  {
    kind: "note",
    body: "Neutral context that does not change what the reader should do.",
  },
  {
    kind: "tip",
    body: "An optional shortcut or a better default once the basics work.",
  },
  {
    kind: "warning",
    body: "A setting that widens what the agent may do without asking.",
  },
  {
    kind: "danger",
    body: "Data loss, or removing the last boundary around execution.",
  },
];

export type Toast = {
  title: string;
  body: string;
  action: string;
  color: string;
  bg: string;
  ring: string;
};

export const toasts: Toast[] = (
  [
    [
      "Command approved",
      "npm run validate is running in the sandbox",
      "#5E9B72",
      "#0F1412",
      "#1C2A20",
      "View",
    ],
    [
      "Reconnecting",
      "Attempt 2 of 5 · session preserved",
      "#E5A33B",
      "#141210",
      "#3A2C1C",
      "Retry",
    ],
    [
      "Sandbox expired",
      "Session 8f3c2a was destroyed after 30 minutes",
      "#8E959B",
      "#0F1113",
      "#24272B",
      "New",
    ],
    [
      "Validation failed",
      "1 test failing in components/Pricing.test.tsx",
      "#C4655C",
      "#141011",
      "#4A2E2C",
      "Open",
    ],
  ] as [string, string, string, string, string, string][]
).map(([title, body, color, bg, ring, action]) => ({
  title,
  body,
  color,
  bg,
  ring,
  action,
}));

export const breakpoints: {
  range: string;
  name: string;
  description: string;
}[] = (
  [
    [
      "< 768",
      "Mobile",
      "Single column. Docs nav and sandbox panels become drawers; approval is a fixed bottom sheet.",
    ],
    [
      "768–1023",
      "Tablet",
      "Docs keeps the sidebar, drops the TOC. Sandbox shows chat plus one collapsible panel.",
    ],
    [
      "1024–1279",
      "Laptop",
      "Full docs three-column at reduced widths. Sandbox right panel collapses to icons on demand.",
    ],
    [
      "≥ 1280",
      "Desktop",
      "Layouts as drawn: 264px docs sidebar, 248/1fr/300 sandbox grid, 820px article measure.",
    ],
  ] as [string, string, string][]
).map(([range, name, description]) => ({ range, name, description }));

export const interactionNotes: [string, string][][] = [
  [
    [
      "Navbar",
      "Sticky at all breakpoints, 64px desktop / 56px mobile, translucent with backdrop blur and a 1px bottom border. The active route gets a filled pill, not an underline. Mobile opens a full-width menu panel below the bar with 44px rows and a focus trap; Escape closes and returns focus to the toggle.",
    ],
    [
      "Docs sidebar",
      "Independent scroll container with the page; the current item is highlighted and scrolled into the sidebar viewport on navigation. Groups are always expanded on desktop. Below 768 it becomes a drawer opened from the breadcrumb bar.",
    ],
    [
      "Docs search",
      "⌘K / Ctrl-K anywhere, or click the field. Results are grouped by kind (page, event, api) and filtered as you type; ↑↓ move, ↵ opens, ⌘↵ opens in a new tab, Escape closes and restores scroll position. Empty query shows recent pages.",
    ],
    [
      "On this page",
      "Headings observed with IntersectionObserver; the active entry gets the orange left bar. Below 1280 the TOC collapses into a disclosure under the breadcrumb, closed by default.",
    ],
    [
      "Panel collapse",
      "Sandbox panels collapse left-to-right as width drops: right details panel first, then the files panel. Below 768 all three regions become a segmented control (Chat / Files / Events) with chat as the default tab.",
    ],
    [
      "Approval flow",
      "An approval.requested event pauses the run, disables the composer, and renders the panel inline at the end of the transcript. Focus moves to Deny (the safe default). Long commands scroll inside the details region; the action row never scrolls away. On mobile it is a bottom sheet pinned above the keyboard.",
    ],
  ],
  [
    [
      "Stop task",
      "Stop is available whenever a task is running. It cancels the in-flight tool, rolls back uncommitted edits from that task, and posts a cancellation summary listing exactly what was undone. A toast offers Undo rollback for 10 seconds.",
    ],
    [
      "Reconnect",
      "On stream loss the status pill turns amber, panels dim to 60% and stop accepting input while retries back off (1s, 2s, 4s, 8s, 16s). The session is server-side, so a successful reconnect replays missed events in order. After 5 failures the state becomes fatal with a copyable session ID.",
    ],
    [
      "Focus management",
      'Visible focus on every control: 2px accent ring, 2px offset, never removed. Dialogs and mobile drawers trap focus and restore it to the trigger on close. Streaming output uses aria-live="polite"; approval requests use aria-live="assertive".',
    ],
    [
      "Keyboard",
      "⌘K search, ⌘⏎ send, ⇧⏎ newline, Escape closes overlays or clears a pending composer, A / D approve or deny while an approval is focused, [ and ] toggle the sandbox side panels.",
    ],
    [
      "Loading transitions",
      "Skeletons only for content that has a known shape (file tree, docs article). Streaming text appends without layout shift; the progress line holds its own row so the transcript does not jump. Minimum 200ms visible state for any spinner to avoid flashing.",
    ],
    [
      "Error transitions",
      "Recoverable errors render inline in the transcript with the failing output collapsed to five lines. Fatal errors replace the chat column with a full-region state card and keep the header visible so the session ID stays copyable.",
    ],
  ],
];
