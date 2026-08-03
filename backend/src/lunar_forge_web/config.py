"""Typed configuration shared by the API and private worker."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DeploymentEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


_LOCAL_WORKER_SECRET = "local-only-worker-secret"


class Settings(BaseSettings):
    """Validated environment configuration with production-safe invariants."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LUNAR_FORGE_WEB_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: DeploymentEnvironment = DeploymentEnvironment.LOCAL
    service_name: str = "lunar-forge-web-api"
    api_version: str = "v1"
    core_version: str = "0.1.0"
    event_schema_version: int = 1
    log_level: str = "INFO"
    cors_allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    supabase_issuer: str = "https://example.supabase.co/auth/v1"
    supabase_jwks_url: str = (
        "https://example.supabase.co/auth/v1/.well-known/jwks.json"
    )
    supabase_audience: str = "authenticated"
    supabase_required_role: str = "authenticated"
    supabase_allowed_algorithms: Annotated[tuple[str, ...], NoDecode] = (
        "ES256",
        "RS256",
    )
    jwks_cache_ttl_seconds: int = Field(default=600, ge=30, le=3_600)
    database_url: str = "sqlite+aiosqlite:///./lunar-forge-web.db"
    worker_shared_secret: SecretStr = SecretStr(_LOCAL_WORKER_SECRET)
    websocket_ticket_ttl_seconds: int = Field(default=60, ge=15, le=300)
    max_event_replay_items: int = Field(default=500, ge=1, le=2_000)
    max_request_body_bytes: int = Field(
        default=1_048_576,
        ge=16_384,
        le=10_485_760,
    )
    fake_auth_enabled: bool = False

    @field_validator(
        "cors_allowed_origins",
        "supabase_allowed_algorithms",
        mode="before",
    )
    @classmethod
    def _parse_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _validate_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        if not origins:
            raise ValueError("At least one CORS origin is required.")
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed.")
        if len(set(origins)) != len(origins):
            raise ValueError("CORS origins must be unique.")
        for origin in origins:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid CORS origin: {origin!r}.")
            if origin.endswith("/"):
                raise ValueError("CORS origins must not include a trailing slash.")
        return origins

    @field_validator("supabase_allowed_algorithms")
    @classmethod
    def _validate_algorithms(cls, algorithms: tuple[str, ...]) -> tuple[str, ...]:
        supported = {"ES256", "RS256"}
        if not algorithms or not set(algorithms).issubset(supported):
            raise ValueError("Only asymmetric ES256 and RS256 JWTs are accepted.")
        return algorithms

    @model_validator(mode="after")
    def _validate_environment(self) -> Self:
        if self.environment is not DeploymentEnvironment.PRODUCTION:
            return self
        if self.fake_auth_enabled:
            raise ValueError("Fake authentication cannot be enabled in production.")
        if any(not origin.startswith("https://") for origin in self.cors_allowed_origins):
            raise ValueError("Production CORS origins must use HTTPS.")
        if not self.supabase_issuer.startswith("https://"):
            raise ValueError("Production Supabase issuer must use HTTPS.")
        if not self.supabase_jwks_url.startswith("https://"):
            raise ValueError("Production Supabase JWKS URL must use HTTPS.")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("Production database URL must use postgresql+asyncpg.")
        secret = self.worker_shared_secret.get_secret_value()
        if secret == _LOCAL_WORKER_SECRET or len(secret) < 32:
            raise ValueError("Production worker secret must be at least 32 characters.")
        return self


def get_settings() -> Settings:
    """Load settings from the process environment."""

    return Settings()
