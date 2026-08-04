# Core agent adapter

## Pinned development source

The backend development environment installs the sibling `lunar-forge`
project as an editable uv path source from `../../lunar-forge`. The source
inspected and tested for this adapter is:

- package version: `0.1.0`;
- Git commit: `eb0ddb5de76ad6da11c0653384d7b7efcac2d9f7`;
- branch: `feature/web-runtime-api`;
- exact tag at that commit: none;
- recorded: 2026-08-04.

The machine-readable record is in `backend/core-source.json`.

## Stable public symbols

Production adapter and runtime code import only these symbols from the
`lunar_forge` package root:

- `AgentEvent`;
- `AgentRequest`;
- `ApprovalDecision`;
- `ApprovalRequest`;
- `CancellationToken`;
- `ModelClient`;
- `WorkspaceRuntime`;
- `create_ephemeral_model_client`;
- `run_agent_events`.

The hosted runtime bridge additionally uses the public portable runtime values
`RuntimeCheckpoint`, `RuntimeCommandResult`, `RuntimeFileInfo`,
`RuntimeNetworkPolicy`, `RuntimeOperationResult`, `RuntimePathType`,
`RuntimeRollbackResult`, `RuntimeRollbackStatus`, `RuntimeTextResult`, and
`RuntimeWriteResult`; the documented runtime bounds; and
`normalize_workspace_path`.

It uses `AgentRequest` for construction, calls `run_agent_events` with the
public runtime, ephemeral model client, cancellation token, and live-event
callback, serializes each `AgentEvent` through its public `to_dict()` method,
and implements the public synchronous approval-provider shape. It does not import
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

The runtime, model-injection, cancellation, rollback-event, and event-streaming
capabilities required by the worker are public on the pinned branch. Two gaps
remain: there is no public manual session-compaction operation, and
`ApprovalDecision.source` has no `web` value. Manual `compact_session` therefore
returns `false` while automatic compaction events are forwarded. The Redis
approval bridge uses the public `textual` source as a compatibility value; this
does not import or execute Textual code.

The real adapter is selected only by the private worker. Tests use injected
public `ModelClient` and `WorkspaceRuntime` fakes. A live-model contract is
skipped unless
`LUNAR_FORGE_WEB_RUN_LIVE_MODEL_TESTS=1` and provider credentials are explicitly
configured.
