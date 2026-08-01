# LunarForge Web Architecture Decisions

## Status

Accepted architecture for the first private portfolio deployment, based on the completed Claude Design frontend and the selected hosting/security decisions.

## Existing frontend

- Next.js App Router at repository root.
- Next.js 15.5.4, React 19.1.1, TypeScript, CSS Modules.
- Claude Design source files remain unchanged in `project/`.
- Existing routes and visual behavior are preserved.
- `src/app/sandbox/SandboxApp.tsx` is currently a scripted demo and will be connected to real services incrementally.
- `src/lib/docs.ts` is currently static and contains links to pages that still need implementation.

## Public and protected routes

Public:

- landing page;
- documentation;
- comparison route;
- design-system route;
- legal/security pages;
- login.

Protected:

- sandbox;
- administration.

## Authentication

- Supabase Auth.
- Individual invite-only accounts.
- Password login after accepting an invite.
- Permanent owner/admin password account.
- TOTP MFA required for admin.
- No universal shared password.
- FastAPI validates JWTs and performs all ownership/role checks.

## Hosting

- Frontend: Vercel.
- API: Google Cloud Run FastAPI service.
- Turn worker: separate private Google Cloud Run service.
- Database: Neon PostgreSQL.
- Ephemeral coordination/events/rate limits: Upstash Redis.
- Secrets: Google Secret Manager.
- Primary sandbox runtime: E2B.
- Later runtime: separate self-hosted Docker worker, admin-only initially.

## Real-time model

- WebSocket between browser and FastAPI.
- One-time Redis-backed WebSocket tickets, rather than JWTs in the query string.
- Worker appends structured LunarForge events to a bounded Redis Stream.
- API relays and replays events by sequence.
- Cloud Run disconnects are handled through reconnect and `after_sequence` replay.

## Model funding

Owner-funded:

- OpenAI;
- one server-approved model;
- maximum reasoning effort `high`;
- 20 turns per user per day;
- one active sandbox per user;
- 15-minute turn timeout;
- USD 3 daily estimated-cost cap per user;
- USD 10 global daily estimated-cost cap;
- global admin disable switch.

BYOK:

- OpenAI and Anthropic initially;
- key kept only in browser memory and worker memory for a turn;
- browser resends it per turn;
- reload requires re-entry;
- never persisted or placed inside E2B;
- additional LiteLLM providers later by allowlist.

## Sandbox lifecycle

- E2B default runtime.
- 30-minute inactivity TTL.
- meaningful activity extends TTL.
- one active sandbox per user initially.
- project and detailed session data exist only while sandbox is active.
- active project can be downloaded.
- content is deleted at expiry.
- minimal usage/security/audit metadata retained for 30 days.

## Initial project sources

First release:

- approved templates;
- public GitHub repositories.

Later:

- bounded local uploads;
- private GitHub repositories using GitHub App/OAuth installation tokens.

Raw personal access tokens and host-path mounts are not supported.

## Network

- denied by default;
- explicit approval required for installs, clones, external browser validation, and other network actions;
- provider-enforced egress restrictions are required;
- if the pinned E2B SDK cannot safely enforce per-operation or allowlisted egress, the feature remains unavailable rather than pretending an application-level toggle is isolation.

## Approvals

Always approval-gated:

- dependency installation;
- network access;
- private/public clone operations with side effects;
- Git commit;
- browser/dev-server startup;
- external MCP/plugin effects;
- risky commands;
- any action required by the LunarForge core policy.

## Cancellation

- stop model and active command where supported;
- invoke current-turn rollback;
- report exactly what was reverted, retained, or could not be reverted.

## Live preview

- interactive embedded preview;
- authenticated owner only;
- short-lived signed ticket;
- separate preview origin/gateway;
- restrictive iframe sandbox;
- expires with sandbox;
- E2B access tokens never reach the browser.

## Persistence

While active:

- transcript;
- bounded events;
- summaries;
- files;
- artifacts;
- approvals;
- bounded command output;
- usage.

Deleted at expiry:

- all content and temporary credentials.

Retained for 30 days:

- IDs and timestamps;
- provider/model identifiers;
- token/cost totals;
- approval/audit metadata;
- error codes;
- cleanup result.

## Later Docker provider

- separate worker host;
- one container per sandbox;
- admin-only initially;
- no privileged mode or arbitrary mounts;
- same public runtime interface and API contracts as E2B.
