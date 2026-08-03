# LunarForge Web backend

One Python 3.11+ project exposes two independent ASGI entrypoints:

- `lunar_forge_web.api.main:app` — browser-facing `/api/v1` FastAPI API.
- `lunar_forge_web.worker.main:app` — private turn worker with
  `POST /internal/v1/turns:run`.

This phase is contract-first and deterministic. Repositories are in memory, the
runtime and agent are fakes, WebSocket tickets are process-local, and no call is
made to E2B, Neon, Upstash, Supabase APIs, or a model. JWT signatures are still
verified against the configured Supabase issuer and asymmetric JWKS; tests use
a deterministic P-256 key.

```powershell
uv sync --extra dev
uv run pytest -q
uv run python -B -m compileall src
```

From the repository root, `python scripts/export_openapi.py` writes reviewable
API and worker OpenAPI documents. `npm run api:generate` then regenerates the
typed frontend client.
