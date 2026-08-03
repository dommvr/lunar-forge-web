import json
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from lunar_forge_web.api.main import create_app
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import SessionSettings, WorkerTurnRequest
from lunar_forge_web.storage.orm import Base
from lunar_forge_web.worker.main import create_worker_app


def test_contracts_are_bounded_strict_and_json_safe():
    with pytest.raises(ValidationError):
        WorkerTurnRequest(
            sandbox_id="sandbox-a",
            session_id="session-a",
            turn_id="turn-a",
            owner_id="user-a",
            message="x" * 50_001,
        )
    with pytest.raises(ValidationError):
        SessionSettings(extra_field=True)
    with pytest.raises(ValidationError):
        AgentEventContract(
            event_id="evt-a",
            session_id="session-a",
            turn_id="turn-a",
            sequence=1,
            timestamp="2026-01-01T00:00:00Z",
            type="status.updated",
            payload={"not_json": object()},
        )


def test_openapi_contains_versioned_contracts(settings, container):
    api_schema = create_app(settings, container).openapi()
    worker_schema = create_worker_app(settings, container).openapi()

    assert api_schema["openapi"].startswith("3.1")
    assert {
        "/api/v1/health",
        "/api/v1/version",
        "/api/v1/capabilities",
        "/api/v1/me",
        "/api/v1/realtime/tickets",
    }.issubset(api_schema["paths"])
    assert "/internal/v1/turns:run" in worker_schema["paths"]
    assert "AgentEventContract" in worker_schema["components"]["schemas"]
    json.dumps(api_schema, allow_nan=False)
    json.dumps(worker_schema, allow_nan=False)


def test_sqlalchemy_metadata_covers_accepted_data_model():
    assert {
        "users",
        "invites",
        "project_sources",
        "sandboxes",
        "sessions",
        "turns",
        "approvals",
        "event_offsets",
        "artifacts",
        "previews",
        "usage_ledger",
        "daily_quota_counters",
        "admin_settings",
        "cleanup_jobs",
        "audit_events",
    } == set(Base.metadata.tables)


def test_openapi_exports_are_current():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_openapi.py"), "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_initial_alembic_migration_upgrades_and_downgrades():
    backend = Path(__file__).resolve().parents[1]
    configuration = Config(str(backend / "alembic.ini"))
    command.upgrade(configuration, "head")
    command.downgrade(configuration, "base")
