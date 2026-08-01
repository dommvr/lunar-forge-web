# LunarForge Web

Next.js implementation of the `Product UI design system` handoff bundle from
[Claude Design](https://claude.ai/design).

The original HTML/CSS/JS prototypes are kept unchanged in [`project/`](project/)
and remain the source of truth for visual decisions. Everything under `src/` is
the real build.

```bash
npm install
npm run dev
```

| Script | Does |
| --- | --- |
| `npm run dev` | Dev server on http://localhost:3000 |
| `npm run build` | Production build |
| `npm run validate` | `tsc --noEmit` then `next build` |

## Routes

| Route | Source design | Notes |
| --- | --- | --- |
| `/` | `Landing.dc.html` | Hero with transcript preview, capabilities, safety model, flow, workflow, developer surface, CTA. Carries the fixed ember field. |
| `/docs` | `Docs.dc.html` | Overview with sidebar navigation. |
| `/docs/permissions-and-approvals` | `Docs.dc.html` | Three-column article: sidebar, prose, live table of contents. |
| `/sandbox` | `Sandbox.dc.html` | The chat/files/details application shell. |
| `/compare` | `Comparison.dc.html` | Benchmark scoreboard, phase and token charts, full run record. |
| `/design-system` | `Design System.dc.html` | Internal reference: tokens, component gallery, interaction notes, sandbox state matrix. |

## Structure

```
src/
  app/
    globals.css                     design tokens + base layer
    layout.tsx                      fonts, metadata, ⌘K provider
    page.tsx                        landing
    docs/                           docs layout, overview, article
    sandbox/                        sandbox shell + state machine
    compare/                        comparison route
    design-system/                  token and component reference
  components/
    SiteNav / SiteFooter            shared chrome (marketing + docs variants)
    CommandMenu / SearchProvider    ⌘K palette, one instance app-wide
    EmberField                      viewport-fixed canvas background
    docs/                           sidebar, mobile drawer, table of contents
    ui/                             Button, Callout, CodeBlock
  lib/                              route content, extracted verbatim
```

Styling is plain CSS Modules over the custom properties in `globals.css`. Token
names match the published design-system table one-for-one, so a value change
there propagates everywhere.

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
- **Sandbox.** There is no backend, so the route runs a scripted local session:
  picking a prompt drives ready → working → approval gate → validation → done,
  with Deny and Stop as the other exits. All thirteen documented states are
  modelled in `src/lib/sandbox.ts` and rendered in the matrix on
  `/design-system`; the live route implements the six that a session can reach
  without a server.
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
