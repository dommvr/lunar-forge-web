import json
import logging

import pytest
from pydantic import SecretStr, ValidationError

from lunar_forge_web.config import (
    DeploymentEnvironment,
    InfrastructureBackend,
    Settings,
    TurnExecutionBackend,
)
from lunar_forge_web.security.redaction import REDACTED, RedactingJsonFormatter, redact


def test_redaction_removes_nested_credentials_and_bearer_values():
    payload = redact(
        {
            "authorization": "Bearer top-secret",
            "nested": {
                "api_key": "sk-secret-value-12345678",
                "message": "token=another-secret",
            },
        }
    )
    serialized = json.dumps(payload)

    assert payload["authorization"] == REDACTED
    assert payload["nested"]["api_key"] == REDACTED
    assert "top-secret" not in serialized
    assert "another-secret" not in serialized
    assert "sk-secret" not in serialized


def test_structured_formatter_redacts_log_events():
    secret = "sk-byok-ephemeral-proof-123456789"
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ignored", (), None)
    record.event = {
        "event": "test",
        "password": "do-not-log",
        "provider_api_key": secret,
    }
    output = RedactingJsonFormatter().format(record)

    assert json.loads(output)["password"] == REDACTED
    assert json.loads(output)["provider_api_key"] == REDACTED
    assert "do-not-log" not in output
    assert secret not in output


def test_production_settings_reject_insecure_defaults():
    with pytest.raises(ValidationError):
        Settings(environment=DeploymentEnvironment.PRODUCTION)

    settings = Settings(
        environment=DeploymentEnvironment.PRODUCTION,
        cors_allowed_origins=("https://app.example.com",),
        supabase_issuer="https://project.supabase.co/auth/v1",
        supabase_jwks_url=(
            "https://project.supabase.co/auth/v1/.well-known/jwks.json"
        ),
        database_url="postgresql+asyncpg://user:pass@db.example.com/app",
        infrastructure_backend=InfrastructureBackend.NEON_UPSTASH,
        redis_url=SecretStr("rediss://default:secret@redis.example.com:6379"),
        redis_key_prefix="lfw:production",
        e2b_api_key=SecretStr("e2b_test_production_key"),
        owner_funded_model="openai/gpt-production",
        owner_funded_input_cost_microusd_per_million=1_000_000,
        owner_funded_output_cost_microusd_per_million=2_000_000,
        worker_shared_secret=SecretStr("x" * 40),
        worker_url="https://worker.example.run.app",
        worker_audience="https://worker.example.run.app",
        turn_execution_backend=TurnExecutionBackend.PRIVATE_WORKER,
    )
    assert settings.environment.value == "production"
