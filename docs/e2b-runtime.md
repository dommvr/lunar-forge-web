# E2B runtime

LunarForge Web pins the Python SDK to `e2b==2.37.0`. E2B is the default
non-test `RuntimeProvider`; the deterministic fake remains the test substitute.
The LunarForge agent loop and model client run in the private worker. E2B runs
project commands and exposes bounded project files only.

## Templates

- `lfw-python-cli-v1`: Python, Git/ZIP tooling, and a wheel built from the exact
  core revision in `backend/core-source.json`.
- `lfw-static-site-v1`: a minimal HTML/CSS workspace and Git/ZIP tooling.
- `lfw-vite-react-v1`: pinned Vite, TypeScript, React, and Git/ZIP tooling, with
  dependencies installed during the template build.

`scripts/build_e2b_templates.py` copies the minimum core source to a temporary
directory under `e2b/.build` before building its wheel. It refuses a core
revision that differs from `backend/core-source.json` and never writes build
output into the sibling core checkout.

Each template is built with two vCPUs and 2,048 MiB memory. Actual disk size is
reported from E2B sandbox metadata because the pinned template build API does
not expose a disk-size setting.

## Enforced runtime policy

Creation explicitly sets secure access, disables public inbound traffic,
denies all outbound traffic, installs no environment variables, sets a
30-minute timeout, and selects kill rather than pause on expiry. The provider
verifies ownership metadata and deny-all status after creation and reconnect.
Only meaningful application activity calls `set_timeout(1800)`; passive browser
heartbeats do not.

E2B 2.37.0 exposes an atomic network-policy update. Approved GitHub clone, npm,
and pip operations are serialized per sandbox, limited to operation-specific
hostnames while retaining deny-all for every other destination, and wrapped in
a `finally` block that restores and verifies the empty allowlist:

- GitHub: `api.github.com`, `github.com`
- npm: `registry.npmjs.org`
- pip: `pypi.org`, `files.pythonhosted.org`

Public Git clone additionally requires HTTPS `github.com`, rejects credentials,
ports, queries, fragments, non-GitHub hosts, submodules, symlinks, and redirects,
uses a shallow no-tags clone, and enforces 120-second and 250 MB limits. The
GitHub metadata size is checked before clone, and extracted size and file count
are checked again before the workspace is replaced. The clone method is
intended to be called only after the web approval flow resolves.

Arbitrary external browser validation remains unavailable. Although E2B can
allow one hostname, redirect-safe destination enforcement for a general browser
request is not implemented, so the capability is reported unavailable rather
than exposing a UI-only toggle.

## Bounds and cleanup

Commands are limited to 20,000 characters and 15 minutes. Output is redirected
inside the sandbox and streamed back with independent 100,000-character bounds,
then redacted. Browser file reads are workspace-confined, hide credential and
runtime metadata paths, skip symlinks, and return at most 1 MB. Project archives
exclude `.git`, `.agent`, `.lunar-forge`, `.ssh`, credentials, and symlinks and
are capped at 10 MB (and by the API response limit). Artifacts are listed only
from `.lunar-forge/artifacts` and are capped at 10 MB each.

Explicit deletion, reset, and expiry reconciliation call E2B kill. A missing
remote sandbox is treated as already deleted so cleanup is idempotent.

## Live verification

The live smoke test is opt-in:

```powershell
$env:E2B_API_KEY = "..."
$env:LUNAR_FORGE_WEB_E2B_LIVE_TEMPLATE = "lfw-python-cli-v1"
uv run pytest -q -m live_e2b tests/test_e2b_runtime_live.py
```

Without both variables it is reported as skipped, not passed.
