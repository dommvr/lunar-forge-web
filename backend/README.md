# LunarForge Web backend

One Python 3.11+ project exposes two independent ASGI entrypoints:

- `lunar_forge_web.api.main:app` — browser-facing `/api/v1` FastAPI API.
- `lunar_forge_web.worker.main:app` — private turn worker with
  `POST /internal/v1/turns:run`.

The backend now has production persistence adapters for Neon PostgreSQL and
Upstash Redis. Deterministic in-memory repositories remain available for tests;
E2B is the default non-test runtime and the LunarForge public API adapter runs
the agent in the private worker. Tests select deterministic fakes explicitly.
JWT signatures are verified against the configured Supabase issuer and
asymmetric JWKS; tests use a deterministic P-256 key.

```powershell
uv sync --extra dev
uv run pytest -q
uv run python -B -m compileall src
```

Production sets `LUNAR_FORGE_WEB_INFRASTRUCTURE_BACKEND=neon_upstash`, a pooled
`LUNAR_FORGE_WEB_DATABASE_URL`, a direct
`LUNAR_FORGE_WEB_MIGRATION_DATABASE_URL`, and a TLS `rediss://` Upstash URL.
See `docs/persistence.md` and `infra/local/docker-compose.yml`.

The production runtime additionally requires
`LUNAR_FORGE_WEB_RUNTIME_BACKEND=e2b`, `LUNAR_FORGE_WEB_E2B_API_KEY`, and the
three built template aliases. See `docs/e2b-runtime.md`. The E2B key is a
runtime-control credential; model provider keys are never placed in E2B.

From the repository root, `python scripts/export_openapi.py` writes reviewable
API and worker OpenAPI documents. `npm run api:generate` then regenerates the
typed frontend client.
