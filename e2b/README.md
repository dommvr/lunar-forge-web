# LunarForge Web E2B templates

These templates are built with the backend's pinned `e2b==2.37.0` SDK. They
contain project tooling only. The LunarForge agent and model client continue to
run in the private Cloud Run worker, and no model provider credential is copied
into a template or sandbox environment.

Build all templates from the web repository root:

```powershell
$env:LUNAR_FORGE_CORE_PATH = "C:/Users/tiron/Desktop/lunar-forge"
cd backend
uv run python ../scripts/build_e2b_templates.py
```

The build script verifies the core source revision recorded in
`backend/core-source.json`, copies the minimum package source into a temporary
directory under `e2b/.build`, builds a wheel there, and uploads the template
definitions. The sibling core checkout remains read-only.

Runtime network policy is not defined by these build-time package downloads.
The production adapter creates every sandbox with secure access, public inbound
traffic disabled, and outbound traffic denied. Only approved operations can
temporarily replace egress with a provider-enforced hostname allowlist.
