# Frontend baseline and manual visual checklist

Baseline recorded on 2026-08-01 before backend integration. The implementation
is Next.js 15.5.4, React 19.1.1, strict TypeScript, and CSS Modules at the
repository root. The current sandbox is a deterministic browser-only state
fixture, and the comparison route uses illustrative sample data.

Core product claims were checked against the read-only sibling repository at
commit `e4f4d0a09e81e88a4fc9300767c7b0dbee4aa5fe` (2026-07-29), package version
`0.1.0`. The stable package front door is `lunar_forge`; the console command is
`lunar-forge`; project configuration is `.agent/config.yaml`; and the public
event envelope uses names such as `permission.requested`.

## Visual source freeze

The Claude Design files under `project/` remain the visual source of truth and
must not be edited during product implementation. Their baseline SHA-256 hashes
are:

| File | SHA-256 |
| --- | --- |
| `Comparison.dc.html` | `0757D6A3DB255045B92810E11114BA196659F6BFE008DE3DFF244248C2EA259B` |
| `Design System.dc.html` | `265852719E4FA1339F1805F20063B275C059993374F964B619E47628AB2AF783` |
| `Docs.dc.html` | `B78C78576DB8A6E4C878FDD2C0C1E9A97E90AB74CB465C8B3132830AED1E3BE6` |
| `Landing.dc.html` | `EE2249DF5975D2D2904A79697C56DFDFA671707D43A5A6306027AFD76EE0C6B0` |
| `Sandbox.dc.html` | `A2198805D5764F7AD093C55554CAF1182ECF3D00F2FB68F6F6F00F4A1B17FB9E` |

## Review setup

Run `npm run dev`, then inspect at 1440 × 900, 1024 × 768, 768 × 1024, and
390 × 844. At every route, confirm the graphite/orange token system, IBM Plex
fonts, 2px focus treatment, keyboard reachability, and absence of horizontal
page overflow. Use reduced-motion mode once to confirm motion is suppressed
without hiding content.

## `/`

- Confirm the sticky translucent navigation, active Home pill, hero proportions,
  transcript card, CTA order, and footer match `Landing.dc.html`.
- Confirm embers stay viewport-fixed, appear only on the landing page, pause
  when the document is hidden, and become a static field with reduced motion.
- At mobile width, confirm five capability cards are initially shown and the
  disclosure reveals all ten without reordering them.
- Confirm factual copy shows core `v0.1.0`, `lunar-forge`, `lunar_forge`,
  `AgentRequest`, and `run_agent_events` without changing the code-block hierarchy.

## `/docs`

- Confirm the docs navbar, independent sidebar, overview measure, start cards,
  and tile grid match the overview frame in `Docs.dc.html`.
- Confirm the current sidebar item scrolls into view and the mobile breadcrumb
  opens a focus-managed documentation drawer.
- Confirm command search opens by click and Ctrl/Command-K, filters results, and
  supports arrow navigation, Enter, modified Enter, and Escape.

## `/docs/permissions-and-approvals`

- Confirm the desktop sidebar/article/TOC proportions and mobile drawer/TOC
  disclosures match `Docs.dc.html`.
- Scroll through every heading and confirm the active TOC marker follows the
  visible section and anchor links land below the sticky navigation.
- Confirm long code and option tables scroll internally rather than widening the
  page.
- Confirm examples show `.agent/config.yaml`, `permissions.mode`, the
  `lunar-forge` CLI, and a versioned `permission.requested` `AgentEvent` envelope.

## `/sandbox`

- Confirm the desktop 248px/files, flexible chat, and 300px/details rhythm and
  the matching dark application chrome from `Sandbox.dc.html`.
- Confirm the page labels itself as a scripted preview and no interaction makes
  a network request or executes a command.
- Start a fixture prompt and confirm progress/tool rows appear in order. When the
  approval panel opens, focus must move to Deny, the composer must be disabled,
  long command details must scroll, and the action row must remain available.
- At 390px, confirm Chat/Files/Events operate as mutually exclusive segmented
  panels and the approval appears as a bottom sheet above the composer.
- Exercise Approve, Deny, Stop, and Reset and confirm the visible state remains
  consistent with the thirteen-state matrix on `/design-system`.

## `/compare`

- Confirm the scoreboard, phase bars, token bars, run-record table, diff cards,
  methodology split, and CTA preserve `Comparison.dc.html` at desktop and mobile.
- Confirm all values are visibly described as illustrative fixtures and no copy
  claims a run log or benchmark harness exists.
- Confirm the wide table scrolls inside its container and the mobile metric rows
  replace it at the intended breakpoint.

## `/design-system`

- Confirm token swatches match `src/app/globals.css`, typography specimens use
  the correct font family, and buttons/callouts/code blocks retain their states.
- Confirm the interaction notes identify the future backend boundary and use the
  core event name `permission.requested`.
- Confirm all thirteen sandbox state cards render with the expected tone,
  progress, and actions without implying they are live backend states.

## Automated baseline

- Vitest covers active navigation, the mobile menu, command-menu keyboard
  behavior, current docs navigation, intersection-driven TOC state, approval
  safe focus, and mobile sandbox segments.
- Playwright performs a Chromium render smoke check for all six implemented
  route URLs.
- The required command sequence is `npm run lint`, `npm run typecheck`,
  `npm test`, `npm run build`, `npm run test:e2e`, and `git diff --check`.
