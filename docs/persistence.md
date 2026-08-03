# Persistence and retention

LunarForge Web uses Neon PostgreSQL for durable application metadata and
Upstash Redis for bounded, ephemeral coordination. The deterministic in-memory
adapters remain the default in tests. Production configuration rejects the
in-memory backend.

## PostgreSQL

Alembic owns the schema; production startup never creates tables. Application
traffic should use a Neon pooled `postgresql+asyncpg` URL. Alembic should use a
direct Neon URL in `LUNAR_FORGE_WEB_MIGRATION_DATABASE_URL` because schema
migrations should not run through the pooler.

The database enforces one active sandbox per owner with a partial unique index.
Quota reservations and the user/global daily counters are updated in one
transaction with row locks. Costs are stored as integer micro-US dollars.

## Redis keys

All keys start with the environment-specific `redis_key_prefix`.

```text
{prefix}:events:{session_id}                    bounded event Stream
{prefix}:event-sequence:{session_id}            last accepted sequence
{prefix}:controls:{session_id}                  bounded approval/cancel Stream
{prefix}:ticket:ws:{sha256_digest}              one-use WebSocket grant
{prefix}:ticket:preview:{sha256_digest}         one-use preview grant
{prefix}:ticket-index:ws:{session_id}           cleanup index
{prefix}:ticket-index:preview:{sandbox_id}      cleanup index
{prefix}:rate:{scope}:{identifier}              fixed-window counter
{prefix}:lock:{name}                            short compare-and-delete lease
```

Ticket plaintext is returned once and never stored. Event append uses one Lua
script to validate the next sequence, append the event, trim the Stream to
2,000 items, and refresh bounded TTLs. Control Streams contain only redacted,
bounded approval or cancellation messages and retain at most 200 items.

BYOK values are not modeled in PostgreSQL or Redis. Credential-shaped fields
in event and control payloads are redacted before serialization.

## Expiry and retention

Only meaningful activity extends a sandbox by 30 minutes: sending a turn,
resolving an approval, active agent progress, opening an authenticated preview,
or explicit file/artifact interaction. Heartbeats do not extend lifetime.

Reconciliation first terminates the runtime and removes Redis session/ticket
state. It then deletes project sources, artifacts, previews, and event offsets;
clears prompts, session settings, and approval details; and leaves bounded
tombstones plus usage/audit/cleanup metadata. Those retained rows expire after
30 days and are deleted by the retention purge.

## Optional local services

`infra/local/docker-compose.yml` runs local PostgreSQL and Redis only for
development and contract testing:

```powershell
docker compose -f infra/local/docker-compose.yml up -d
```

Copy values from `infra/local/.env.example` into a private local environment
file. Production remains Neon and Upstash and requires TLS for Redis.
