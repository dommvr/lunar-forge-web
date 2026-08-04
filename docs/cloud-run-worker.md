# Deployed Cloud Run worker smoke test

This smoke test is opt-in. It spends model and E2B quota and requires an invited
test user. It is not part of the deterministic test suite.

## Preconditions

- API and worker images were built from core commit
  `eb0ddb5de76ad6da11c0653384d7b7efcac2d9f7` on
  `feature/web-runtime-api`.
- The worker is private, has concurrency `1`, and has a `960` second timeout.
- Only the API service account has `roles/run.invoker` on the worker.
- The worker, but not the API, has the owner-funded model secret.
- Both services use the same Neon database, Upstash Redis namespace, and
  worker shared secret.
- Live E2B network policy reports deny-all before the turn.

## Opt-in procedure

1. Export the deployed API URL and a short-lived Supabase access token into the
   current shell. Do not place either token in a file or command history.
2. Create an E2B sandbox and session through the authenticated API.
3. Request a one-time WebSocket ticket and connect to the returned path.
4. POST one owner-funded turn while keeping the WebSocket open. Confirm ordered
   sequence numbers and `stream.heartbeat` during idle intervals.
5. If an approval appears, resolve it through the authenticated API and confirm
   one `permission.resolved` event.
6. Disconnect after recording a sequence, obtain a new one-time ticket, and
   reconnect with `after_sequence`. Confirm only later events replay.
7. Start a second turn, request cancellation, and wait for `turn.cancelled`,
   `rollback.started`, `rollback.finished`, then the cancelled `turn.finished`.
8. Delete the sandbox and verify E2B deletion plus detailed Redis-stream cleanup.

Record the deployed revisions, timestamps, final event sequences, and whether
each live check passed or was skipped. Never paste BYOK values, authorization
headers, worker request bodies, or E2B access tokens into the report.
