"""Stable string enums used by public contracts and storage rows."""

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class AssuranceLevel(StrEnum):
    AAL1 = "aal1"
    AAL2 = "aal2"


class Availability(StrEnum):
    AVAILABLE = "available"
    FAKE = "fake"
    PLANNED = "planned"
    UNAVAILABLE = "unavailable"


class SandboxStatus(StrEnum):
    CREATING = "creating"
    READY = "ready"
    BUSY = "busy"
    EXPIRED = "expired"
    DELETING = "deleting"
    DELETED = "deleted"
    FAILED = "failed"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPACTING = "compacting"
    CLOSED = "closed"
    EXPIRED = "expired"


class TurnStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class PreviewStatus(StrEnum):
    STARTING = "starting"
    READY = "ready"
    STOPPED = "stopped"
    FAILED = "failed"
    EXPIRED = "expired"


class FundingMode(StrEnum):
    OWNER_FUNDED = "owner_funded"
    BYOK = "byok"


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
