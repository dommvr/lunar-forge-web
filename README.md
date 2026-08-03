# LunarForge Web

Next.js implementation of the `Product UI design system` handoff bundle from
[Claude Design](https://claude.ai/design).

The original HTML/CSS/JS prototypes are kept unchanged in [`project/`](project/)
and remain the source of truth for visual decisions. Everything under `src/` is
the real build.

```bash
npm ci
npm run dev
```

| Script | Does |
| --- | --- |
| `npm run dev` | Dev server on http://localhost:3000 |
| `npm run lint` | ESLint flat-config checks using the pinned Next.js rules |
| `npm run typecheck` | Strict TypeScript check without emitting files |
| `npm test` | Vitest component tests in jsdom |
| `npm run build` | Production build |
| `npm run test:e2e` | Playwright Chromium smoke suite for every implemented route |
| `npm run docs:generate` | Generate committed navigation, search, and TOC metadata from MDX |
| `npm run docs:links` | Reject missing docs routes and heading anchors |
| `npm run docs:sync` | Fingerprint the allowlisted core sources named by `LUNAR_FORGE_CORE_PATH` |
| `npm run test:sync` | Standard-library tests for sync path and preservation rules |
| `npm run api:generate` | Export both OpenAPI documents and regenerate the typed frontend client |
| `npm run api:check` | Fail when committed OpenAPI documents or generated TypeScript are stale |
| `npm run validate` | Lint, typecheck, unit/link/sync/API checks, then production build |

## Baseline architecture

- Next.js `15.5.4` App Router and React `19.1.1` live at the repository root.
- TypeScript is strict; styling is CSS Modules over tokens in
  `src/app/globals.css`; IBM Plex Sans and Mono are loaded through `next/font`.
- `SearchProvider` owns one application-wide command menu. Marketing routes
  share `SiteNav` and `SiteFooter`; docs add their sidebar, drawer, and table of
  contents in the docs layout.
- Supabase Auth uses SSR cookie refresh and server-verified claims. `/sandbox`
  requires an invited account; `/admin` additionally requires a server-assigned
  role and TOTP `aal2` verification.
- `/sandbox` uses the public FastAPI contracts and one-time-ticket WebSocket
  replay after sign-in. Its current runtime and agent remain deterministic,
  offline fakes; no real LunarForge model turn or hosted container is created.
- `/compare` is an illustrative presentation fixture. Its numbers are sample
  data, not measured benchmark results.
- `backend/` is one Python project with separate public API and private worker
  ASGI entrypoints. This contract phase uses in-memory repositories, an
  offline fake runtime, a deterministic fake agent, and process-local tickets;
  there is no E2B, Neon, Upstash, or real model integration yet.

The factual source for product behavior is the read-only sibling core checkout
at `../lunar-forge`. The audit in this baseline used core commit
`e4f4d0a09e81e88a4fc9300767c7b0dbee4aa5fe` (2026-07-29), package version
`0.1.0`, and its public `lunar_forge` exports. See
[`docs/frontend-baseline.md`](docs/frontend-baseline.md) for the manual visual
checklist and preserved design-source hashes.

## Routes

| Route | Source design | Notes |
| --- | --- | --- |
| `/` | `Landing.dc.html` | Hero with transcript preview, capabilities, safety model, flow, workflow, developer surface, CTA. Carries the fixed ember field. |
| `/docs` | `Docs.dc.html` | Content-driven overview with generated sidebar navigation. |
| `/docs/[...slug]` | `Docs.dc.html` | 26 statically generated MDX articles with the existing article, drawer, search, and TOC layout. |
| `/sandbox` | `Sandbox.dc.html` | API/WebSocket-driven chat, files, approvals, validation, artifacts, and rollback over deterministic fake services. |
| `/admin` | Existing design language | Protected MFA-required shell; management data is intentionally not connected. |
| `/compare` | `Comparison.dc.html` | Illustrative comparison fixture: scoreboard, phase and token charts, full run-record layout. |
| `/design-system` | `Design System.dc.html` | Internal reference: tokens, component gallery, interaction notes, sandbox state matrix. |
| `/login`, `/login/reset` | Existing design language | Public password sign-in and account-recovery entry points for invited users. |
| `/auth/setup-password`, `/auth/update-password`, `/auth/mfa` | Existing design language | Session-bound invitation, recovery, and administrator TOTP flows. |
| `/privacy`, `/security`, `/terms` | Existing design language | Public, truthful placeholder policies marked for owner review. |

## Structure

```
src/
  app/
    globals.css                     design tokens + base layer
    layout.tsx                      fonts, metadata, ⌘K provider
    page.tsx                        landing
    docs/                           preserved docs layout + MDX catch-all route
    sandbox/                        sandbox shell + state machine
    compare/                        comparison route
    design-system/                  token and component reference
    login/ + auth/                  Supabase password, invite, recovery, MFA flows
    admin/                          protected shell; no management backend yet
  components/
    SiteNav / SiteFooter            shared chrome (marketing + docs variants)
    CommandMenu / SearchProvider    ⌘K palette, one instance app-wide
    EmberField                      viewport-fixed canvas background
    docs/                           sidebar, mobile drawer, table of contents
    ui/                             Button, Callout, CodeBlock
  generated/docs-manifest.json     committed navigation/search/TOC metadata
  lib/                              route content and MDX source loader
    api/                            generated contracts + authenticated client
    auth/                           browser/server clients, claims, guards, API token
    realtime/                       ticketed WebSocket replay client
content/docs/                       26 reviewed MDX documentation pages
backend/                            FastAPI API + private worker contract project
scripts/                            docs generation, links, bounded core sync
src/lib/api/generated/              committed OpenAPI-derived types and client
e2e/                                Playwright route smoke tests
vitest.setup.ts                     shared DOM-test setup
```

Styling is plain CSS Modules over the custom properties in `globals.css`. Token
names match the published design-system table one-for-one, so a value change
there propagates everywhere.

## Backend contract phase

The API serves `/api/v1/health`, `/api/v1/version`, capabilities, templates,
authenticated identity, deterministic sandbox/session/turn resources,
approvals, cancellation and rollback, compaction, files, artifacts, one-time
realtime tickets, replay WebSockets, and an MFA-gated admin summary. The private
worker exposes `POST /internal/v1/turns:run` behind a server-only bearer secret.
See [`docs/api.md`](docs/api.md) for the complete inventory, configuration, and
generation workflow.

## Authentication

Copy `.env.example` to `.env.local`, configure the two public Supabase project
values, and add the owner Auth UUID to the server-only admin allowlist. Invited
users sign in with individual credentials; there is no public registration or
shared visitor password. See [`docs/auth.md`](docs/auth.md) for email templates,
owner TOTP setup, route decisions, and the deterministic Playwright fake.

## Documentation content pipeline

Every article is a file in `content/docs/`. Required frontmatter supplies its
section and order, release status, core version, verification date, and search
keywords. `scripts/generate_docs_manifest.mjs` extracts level-two and
level-three headings with GitHub-compatible IDs, builds the committed manifest,
and provides the only input to the sidebar, overview cards, pagination, table
of contents, recent pages, and command-menu search. The production build runs
the generator in check mode and fails when content and metadata differ.

The current inventory is: Introduction, Installation, Quick start,
Configuration, CLI usage, Textual chat, Projects and AGENTS.md, File and project
tools, Permissions and approvals, Local execution safety, Docker mode,
Validation, Browser validation, Sessions and resume, Working-memory compaction,
Subagents, MCP, Plugins, Git support, Event protocol, Public Python API,
Troubleshooting, Security model, Hosted sandbox, BYOK and privacy, and
Hosted-sandbox limits. The final three pages are explicitly labelled planned
and do not present the frontend fixture as a released cloud service.

Set `LUNAR_FORGE_CORE_PATH` to the sibling checkout before `npm run docs:sync`.
The sync script reads only its 15-file allowlist: the core README and website
copy, package metadata, root/public API, events, approvals, configuration, MCP
and plugin configuration sources, plus their focused public API, event,
approval, config, and MCP tests. It rejects path escape and `.agent` runtime
data, bounds per-file and total bytes, records the commit/exact tag/date and
SHA-256 fingerprints, extracts literal public exports without importing core,
and preserves a separately marked human-review block.

## Implementation notes

Decisions worth knowing about, all traceable to the design files:

- **Ember field.** Built to the "Hero ember field" spec panel in
  `Landing.dc.html`, not to the mockup's approximation of it. The layer is
  `position: fixed` and viewport-locked, mounted once on the landing route only.
  Density figures are per-viewport (44 particles / 7 per second on desktop, 18 /
  4 on mobile with a 2.4× band); the prototype scaled these by canvas height
  purely because its frame was page-tall. `prefers-reduced-motion` draws a single
  static seeded field with no animation loop, and the loop pauses on
  `document.hidden` only — never on scroll.
- **Sunken sections.** The spec requires sections to stay transparent so the
  fixed layer is not occluded, but the mockup gives several a `#0D0F10` fill.
  Those use a translucent version of that fill — visually the same over the page
  background, which is two units away, while the edge glow still reads through.
- **Sandbox.** The live route is driven by FastAPI responses and ordered public
  events rather than UI timers. The current services remain deterministic and
  offline: they exercise provisioning, turns, approvals, cancellation,
  confirmed rollback, compaction, files, artifacts, and reconnect without
  executing a command or touching the user project. The thirteen-state fixture
  remains in `src/lib/sandbox.ts` for `/design-system` and component tests.
- **Truthful prototype copy.** Visual structure comes from `project/`, while
  product identifiers and examples under `src/` are corrected to match the
  sibling core. The source prototypes themselves remain byte-for-byte unchanged.
- **Mobile capabilities list.** The mockup shows five cards plus "+ 5 more". That
  is implemented as a real disclosure rather than truncation — all ten are
  present, five collapse below 768px.
- **`Compare` in the navbar.** The landing mockup predates the comparison route
  and omits it; the shipped nav includes it so every route is reachable.
- **`support.js`** is the design-tool runtime that renders the `.dc.html`
  prototypes. It is not product code and has no counterpart in `src/`.

## Interaction contract

Behaviours specified in the design system's interaction notes and implemented
here: sticky translucent navbar with a filled pill for the active route; mobile
menu with 44px rows, Escape-to-close and focus return; ⌘K/Ctrl-K search filtered
as you type and grouped by kind, with ↑↓ / ↵ / ⌘↵ / Escape; docs sidebar as an
independent scroll container that scrolls the current item into view; table of
contents driven by `IntersectionObserver`, collapsing to a disclosure below
1280px; sandbox panels collapsing right-to-left, then a Chat/Files/Events
segmented control below 768px; the approval gate pausing the composer, moving
focus to Deny, scrolling long commands inside the details region while the action
row stays pinned, and becoming a bottom sheet on mobile; a 2px accent focus ring
on every interactive element.
