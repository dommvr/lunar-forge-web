# Core agent adapter

## Pinned development source

The backend development environment installs the sibling `lunar-forge`
project as a non-editable uv path source from `../../lunar-forge`. The source
inspected and tested for this adapter is:

- package version: `0.1.0`;
- Git commit: `e4f4d0a09e81e88a4fc9300767c7b0dbee4aa5fe`;
- exact tag at that commit: `core-milestone-1`;
- recorded: 2026-08-03.

The machine-readable record is in `backend/core-source.json`.

## Stable public symbols

Production adapter code imports only these symbols from the `lunar_forge`
package root:

- `AgentEvent`;
- `AgentRequest`;
- `ApprovalDecision`;
- `ApprovalRequest`;
- `run_agent_events`.

It uses `AgentRequest` for construction, calls `run_agent_events`, serializes
each `AgentEvent` through its public `to_dict()` method, and implements the
public synchronous approval-provider shape by duck typing. It does not import
`lunar_forge.agent`, UI modules, runtime internals, private helpers, Rich, or
Textual, and it does not parse console output.

## Event mapping

Core schema-v1 event types and payloads are preserved. Core event IDs and
parent IDs are preserved when they satisfy the web identifier contract;
otherwise the adapter uses a deterministic SHA-256-derived identifier. The
core's local session and turn IDs are replaced with the authoritative web
session and turn IDs. Redis sequence numbers are allocated from the session's
last stored sequence, so a later turn continues the same monotonically
ordered stream.

The public core event has already been bounded and sanitized, and the adapter
applies the web redactor and Pydantic event-size validation again before the
atomic Redis append. Redis performs exact stream trimming at 2,000 events.

The core approval provider is synchronous. The adapter therefore publishes a
bounded `permission.requested` event before waiting on a matching Redis
control, returns an `ApprovalDecision` to core, and publishes the correlated
`permission.resolved` event. Later duplicate permission events emitted by the
core iterator are suppressed by public request ID.

## Public API gaps

The pinned public API does not expose:

- an active-turn cancellation token or cancellation function;
- current-turn rollback invocation;
- manual session compaction;
- an E2B/remote-runtime execution hook (public requests require a local
  `project_root` and expose only `local`, `docker`, and `no-command` modes);
- fake/model-client injection through `run_agent_events`;
- a `web` value for `ApprovalDecision.source`;
- explicit web settings for subagents and parallel subagents.

Consequently, adapter cancellation is cooperative between yielded public
events and reports `rollback_status: unavailable`; it never fabricates a
successful rollback. Confirmed public rollback events are forwarded unchanged.
Manual `compact_session` returns `false`, while automatic compaction events
from a turn are forwarded. Deterministic tests inject a fake public event
runner that emits real `AgentEvent` values, because passing a fake model client
would require a private API. The Redis approval bridge uses the public
`textual` source value as the only interactive UI source available; this is a
tracked compatibility gap, not a Textual dependency.

The real adapter is intentionally not selected by the application container
until an E2B-compatible public runtime boundary and these control operations
exist. The existing deterministic fake remains the default for local and test
flows. A live-model contract exists but is skipped unless
`LUNAR_FORGE_WEB_RUN_LIVE_MODEL_TESTS=1` and provider credentials are explicitly
configured.
