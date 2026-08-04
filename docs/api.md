# Backend API contract

Status: private-worker execution phase; connected to the browser sandbox.

LunarForge Web now contains one Python 3.11+ project in `backend/` with two
independently deployable ASGI applications:

- `lunar_forge_web.api.main:app` is the public FastAPI service.
- `lunar_forge_web.worker.main:app` is the private turn worker.

Both services use typed settings. Local and test environments may use SQLite
and deterministic keys; production settings require HTTPS CORS origins, an
asymmetric Supabase issuer/JWKS endpoint, `postgresql+asyncpg`, and a non-default
worker secret of at least 32 characters. Copy `backend/.env.example` to
`backend/.env` for local development. Never prefix the worker secret, database
credentials, or future service-role secrets with `NEXT_PUBLIC_`.

## Implemented API endpoints

Public system endpoints:

- `GET /api/v1/health`
- `GET /api/v1/version`
- `GET /api/v1/capabilities`
- `GET /api/v1/templates`

Authenticated contract endpoints:

- `GET /api/v1/me`
- `POST /api/v1/sandboxes`
- `GET /api/v1/sandboxes`
- `GET /api/v1/sandboxes/{sandbox_id}`
- `POST /api/v1/sandboxes/{sandbox_id}/reset`
- `DELETE /api/v1/sandboxes/{sandbox_id}`
- `GET /api/v1/sandboxes/{sandbox_id}/files`
- `GET /api/v1/sandboxes/{sandbox_id}/file`
- `POST /api/v1/sandboxes/{sandbox_id}/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/turns`
- `POST /api/v1/sessions/{session_id}/approvals/{approval_id}`
- `POST /api/v1/sessions/{session_id}/cancel`
- `POST /api/v1/sessions/{session_id}/compact`
- `GET /api/v1/sessions/{session_id}/events`
- `GET /api/v1/sessions/{session_id}/artifacts`
- `POST /api/v1/realtime/tickets`
- `WS /api/v1/sessions/{session_id}/stream`
- `GET /api/v1/admin/overview` (server-assigned admin role and `aal2` required)

Private worker endpoint:

- `POST /internal/v1/turns:run`

The worker endpoint accepts one bounded turn request and returns only a bounded
terminal summary. During execution the worker appends schema-v1 LunarForge
events to the session's Upstash Redis Stream. It is protected first by Cloud
Run IAM and an exact-audience Google ID token, then by a separate server-only
bearer secret; it must never be exposed as a browser API.

## Authentication and authorization

The API verifies asymmetric Supabase access-token signatures using issuer JWKS,
then validates issuer, audience, expiry, subject, and the `authenticated` token
role. Application role and suspension are loaded from a server-controlled user
repository; client-editable metadata never grants administrator access.
Ownership dependencies scope sandbox and session access to the authenticated
principal. Admin access additionally requires a server role and `aal2`.

Realtime tickets are random one-time credentials. Only a SHA-256 digest is kept,
and consumption is atomic, ownership-bound, session-bound, and time-limited.
Production tickets are stored as hashes in Upstash Redis and atomically
consumed once. Test substitutes preserve the same contract in process.

The browser reconnects with a newly issued ticket and the last processed
sequence. Replayed duplicates are ignored, sequence gaps return an explicit
replay error, and the reducer restores the held UI phase after the stream
resumes. Heartbeats are transport-only and do not extend sandbox inactivity.

The private worker runs the stable LunarForge public event API against the
owned hosted runtime. It listens to bounded Redis control messages while a turn
is active, bridges approval decisions, and requests public cancellation with
rollback. BYOK credentials remain in browser component memory, are included
only in the current turn request, traverse only the authenticated API-to-worker
request, and are discarded with the ephemeral model client.

## Contracts and storage seam

Pydantic contracts cover identity, capabilities, templates, sandbox and session
lifecycle, turns, approvals, event replay, files, artifacts, previews, settings,
usage, admin summaries, worker turns, and the consistent error envelope. The
event model mirrors core schema version 1 and preserves per-session sequence
semantics without importing terminal UI code.

Async repository protocols and SQLAlchemy metadata define the persistence seam.
Production uses migrated Neon tables plus bounded Upstash streams, controls,
tickets, and locks. `RuntimeProvider` and `CoreAgentAdapter` isolate hosted
execution and the core public API. Deterministic offline substitutes remain the
default under tests.

## OpenAPI and generated TypeScript

The committed public and worker schemas are `backend/openapi.json` and
`backend/openapi.worker.json`. The generated browser contract lives in
`src/lib/api/generated/`.

```powershell
npm run api:generate
npm run api:check
```

`api:check` regenerates into memory and fails on drift. It is part of
`npm run validate`, so a backend schema change must be accompanied by an updated
OpenAPI document and TypeScript client.

## Backend validation

```powershell
cd backend
uv sync --extra dev
uv run pytest -q
uv run python -B -m compileall src
```
