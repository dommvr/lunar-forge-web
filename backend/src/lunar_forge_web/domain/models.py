"""Bounded Pydantic contracts for the browser API and private worker."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from lunar_forge_web.domain.enums import (
    ApprovalStatus,
    AssuranceLevel,
    Availability,
    FundingMode,
    PreviewStatus,
    ReasoningEffort,
    SandboxStatus,
    SessionStatus,
    TurnStatus,
    UserRole,
)
from lunar_forge_web.domain.base import (
    ContractModel,
    Identifier,
    LongText,
    SafePath,
    ShortText,
    utc_now,
)


class HealthResponse(ContractModel):
    status: Literal["ok"] = "ok"
    service: Literal["api", "worker"]
    environment: Literal["local", "test", "production"]


class VersionResponse(ContractModel):
    api_version: str
    backend_version: str
    core_version: str
    event_schema_version: int = Field(ge=1)


class UserRecord(ContractModel):
    id: Identifier
    email: EmailStr
    role: UserRole = UserRole.USER
    suspended: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class Principal(ContractModel):
    id: Identifier
    email: EmailStr
    role: UserRole
    suspended: bool = False
    assurance_level: AssuranceLevel


class MeResponse(ContractModel):
    user: Principal


class CapabilityItem(ContractModel):
    id: Identifier
    status: Availability
    description: ShortText


class RuntimeCapability(ContractModel):
    provider: Identifier
    status: Availability
    network_policy: Literal["offline", "provider_enforced", "unavailable"]
    supports_preview: bool = False
    supports_command_cancellation: bool = False
    supports_ttl_extension: bool = False
    supports_temporary_egress: bool = False
    supports_public_git_clone: bool = False
    inactivity_ttl_seconds: int | None = Field(default=None, ge=1, le=86_400)
    cpu_count: int | None = Field(default=None, ge=1, le=128)
    memory_mb: int | None = Field(default=None, ge=1)


class CapabilitiesResponse(ContractModel):
    api_version: str
    core_version: str
    event_schema_version: int = Field(ge=1)
    runtimes: list[RuntimeCapability] = Field(max_length=10)
    features: list[CapabilityItem] = Field(max_length=100)


class TemplateResponse(ContractModel):
    id: Identifier
    name: ShortText
    description: ShortText
    runtime_provider: Identifier
    status: Availability


class TemplatesResponse(ContractModel):
    items: list[TemplateResponse] = Field(max_length=100)


class SandboxCreateRequest(ContractModel):
    template_id: Identifier


class PublicGitValidateRequest(ContractModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048)]


class PublicGitValidateResponse(ContractModel):
    canonical_url: Annotated[str, StringConstraints(max_length=2_048)]
    owner: Identifier
    repository: Identifier
    clone_supported: bool


class SandboxResponse(ContractModel):
    id: Identifier
    owner_id: Identifier
    template_id: Identifier
    runtime_provider: Identifier
    runtime_reference: Identifier | None = None
    status: SandboxStatus
    created_at: datetime = Field(default_factory=utc_now)
    last_activity_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class SandboxesResponse(ContractModel):
    items: list[SandboxResponse] = Field(max_length=100)


class SessionCreateRequest(ContractModel):
    settings: "SessionSettings | None" = None


class SessionResponse(ContractModel):
    id: Identifier
    sandbox_id: Identifier
    owner_id: Identifier
    status: SessionStatus
    created_at: datetime = Field(default_factory=utc_now)
    last_sequence: int = Field(default=0, ge=0)
    compacted_summary_count: int = Field(default=0, ge=0)


class TurnCreateRequest(ContractModel):
    message: LongText
    settings: "SessionSettings | None" = None


class TurnResponse(ContractModel):
    id: Identifier
    session_id: Identifier
    owner_id: Identifier
    status: TurnStatus
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class CancelResponse(ContractModel):
    turn: TurnResponse
    rollback_report: ShortText


class CompactionResponse(ContractModel):
    session: SessionResponse
    compacted: bool
    summary: ShortText


class ApprovalResponse(ContractModel):
    id: Identifier
    sandbox_id: Identifier
    session_id: Identifier
    turn_id: Identifier
    owner_id: Identifier
    kind: Identifier
    title: ShortText
    summary: ShortText
    details: LongText
    risk: Literal["low", "medium", "high"]
    status: ApprovalStatus = ApprovalStatus.PENDING
    expires_at: datetime


class ApprovalResolutionRequest(ContractModel):
    approved: bool
    reason: Annotated[str, StringConstraints(max_length=1_000)] = ""


class EventReplayResponse(ContractModel):
    session_id: Identifier
    after_sequence: int = Field(ge=0)
    last_sequence: int = Field(ge=0)
    has_more: bool = False
    events: list["AgentEventContract"] = Field(max_length=2_000)


class FileEntry(ContractModel):
    path: SafePath
    kind: Literal["file", "directory"]
    size_bytes: int | None = Field(default=None, ge=0)
    truncated: bool = False


class FilesResponse(ContractModel):
    sandbox_id: Identifier
    items: list[FileEntry] = Field(max_length=10_000)
    truncated: bool = False


class FileContentResponse(ContractModel):
    sandbox_id: Identifier
    path: SafePath
    content: Annotated[str, StringConstraints(max_length=1_000_000)]
    encoding: Literal["utf-8"] = "utf-8"
    truncated: bool = False


class ArtifactResponse(ContractModel):
    id: Identifier
    sandbox_id: Identifier
    session_id: Identifier
    owner_id: Identifier
    name: ShortText
    media_type: Annotated[str, StringConstraints(max_length=200)]
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class ArtifactsResponse(ContractModel):
    items: list[ArtifactResponse] = Field(max_length=1_000)


class SandboxDeleteResponse(ContractModel):
    sandbox_id: Identifier
    deleted: Literal[True] = True


class PreviewCreateRequest(ContractModel):
    port: int = Field(ge=1_024, le=65_535)


class PreviewResponse(ContractModel):
    id: Identifier
    sandbox_id: Identifier
    owner_id: Identifier
    port: int = Field(ge=1_024, le=65_535)
    status: PreviewStatus
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime


class SessionSettings(ContractModel):
    reasoning_effort: ReasoningEffort = ReasoningEffort.MEDIUM
    plan_mode: bool = False
    show_usage: bool = True
    subagents_enabled: bool = True
    parallel_subagents_enabled: bool = False
    funding_mode: FundingMode = FundingMode.OWNER_FUNDED
    provider: Literal["openai", "anthropic"] = "openai"
    model: Identifier = "server-default"


class SessionSettingsPatch(ContractModel):
    reasoning_effort: ReasoningEffort | None = None
    plan_mode: bool | None = None
    show_usage: bool | None = None
    subagents_enabled: bool | None = None
    parallel_subagents_enabled: bool | None = None
    funding_mode: FundingMode | None = None
    provider: Literal["openai", "anthropic"] | None = None
    model: Identifier | None = None


class UsageSummary(ContractModel):
    user_id: Identifier
    date: datetime
    turns: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_microusd: int = Field(ge=0)
    daily_turn_limit: int = Field(ge=0)
    daily_cost_limit_microusd: int = Field(ge=0)


class AdminOverviewResponse(ContractModel):
    users_total: int = Field(ge=0)
    users_suspended: int = Field(ge=0)
    sandboxes_active: int = Field(ge=0)
    turns_today: int = Field(ge=0)
    estimated_cost_today_microusd: int = Field(ge=0)
    cleanup_failures: int = Field(ge=0)
    sandbox_kill_switch_enabled: bool
    owner_funded_enabled: bool


class AdminSettingsResponse(ContractModel):
    sandbox_kill_switch_enabled: bool
    owner_funded_enabled: bool


class AdminSettingsPatch(ContractModel):
    sandbox_kill_switch_enabled: bool | None = None
    owner_funded_enabled: bool | None = None


class RealtimeTicketRequest(ContractModel):
    session_id: Identifier


class RealtimeTicketResponse(ContractModel):
    ticket: Annotated[str, StringConstraints(min_length=32, max_length=512)]
    session_id: Identifier
    expires_at: datetime
    websocket_path: SafePath


class StreamReadyMessage(ContractModel):
    type: Literal["stream.ready"] = "stream.ready"
    session_id: Identifier
    after_sequence: int = Field(ge=0)


class WorkerTurnRequest(ContractModel):
    sandbox_id: Identifier
    session_id: Identifier
    turn_id: Identifier
    owner_id: Identifier
    message: LongText
    settings: SessionSettings = Field(default_factory=SessionSettings)


class WorkerTurnResponse(ContractModel):
    turn_id: Identifier
    status: TurnStatus
    events: list["AgentEventContract"] = Field(max_length=2_000)


class ErrorDetail(ContractModel):
    code: Identifier
    message: ShortText
    request_id: Identifier


class ErrorEnvelope(ContractModel):
    error: ErrorDetail


from lunar_forge_web.domain.events import AgentEventContract  # noqa: E402

SessionCreateRequest.model_rebuild()
TurnCreateRequest.model_rebuild()
EventReplayResponse.model_rebuild()
WorkerTurnResponse.model_rebuild()
