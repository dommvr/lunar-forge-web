"""Storage-facing records which are not browser API contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from lunar_forge_web.domain.models import SandboxResponse


@dataclass(frozen=True, slots=True)
class AdminSettingsRecord:
    sandbox_kill_switch_enabled: bool = False
    owner_funded_enabled: bool = True


@dataclass(frozen=True, slots=True)
class QuotaReservation:
    turn_id: str
    user_id: str
    day: date
    reserved_cost_microusd: int


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    user_id: str
    day: date
    turns: int
    settled_cost_microusd: int
    reserved_cost_microusd: int
    global_settled_cost_microusd: int
    global_reserved_cost_microusd: int


@dataclass(frozen=True, slots=True)
class UsageRecord:
    id: str
    user_id: str
    sandbox_id: str | None
    turn_id: str | None
    day: date
    funding_mode: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_microusd: int
    created_at: datetime
    retention_expires_at: datetime


@dataclass(frozen=True, slots=True)
class CleanupClaim:
    job_id: str
    sandbox: SandboxResponse
    session_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CleanupResult:
    job_id: str
    sandbox_id: str
    status: str
    attempts: int
    result_code: str | None
    completed_at: datetime | None
    retention_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: str
    actor_id: str | None
    event_type: str
    resource_id: str | None
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    retention_expires_at: datetime | None = None

