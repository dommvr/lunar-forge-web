"""Export deterministic API and private-worker OpenAPI documents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from pydantic import SecretStr  # noqa: E402

from lunar_forge_web.api.main import create_app  # noqa: E402
from lunar_forge_web.config import DeploymentEnvironment, Settings  # noqa: E402
from lunar_forge_web.worker.main import create_worker_app  # noqa: E402


OUTPUTS = {
    ROOT / "backend" / "openapi.json": "api",
    ROOT / "backend" / "openapi.worker.json": "worker",
}


def _settings() -> Settings:
    return Settings(
        environment=DeploymentEnvironment.TEST,
        cors_allowed_origins=("https://web.example.invalid",),
        supabase_issuer="https://example.supabase.co/auth/v1",
        supabase_jwks_url=(
            "https://example.supabase.co/auth/v1/.well-known/jwks.json"
        ),
        database_url="sqlite+aiosqlite:///:memory:",
        worker_shared_secret=SecretStr("openapi-only-worker-secret-not-for-runtime"),
        log_level="WARNING",
    )


def _serialize(schema: dict[str, object]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_documents() -> dict[Path, str]:
    settings = _settings()
    return {
        path: _serialize(
            create_app(settings).openapi()
            if service == "api"
            else create_worker_app(settings).openapi()
        )
        for path, service in OUTPUTS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = render_documents()
    if args.check:
        stale = [
            path
            for path, content in documents.items()
            if not path.exists() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            print("OpenAPI output is stale: " + ", ".join(str(path) for path in stale))
            return 1
        print("OpenAPI documents are current.")
        return 0
    for path, content in documents.items():
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
