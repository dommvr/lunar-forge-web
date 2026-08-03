"""SQLAlchemy metadata for the accepted application data model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserRow(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class InviteRow(TimestampMixin, Base):
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectSourceRow(TimestampMixin, Base):
    __tablename__ = "project_sources"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SandboxRow(TimestampMixin, Base):
    __tablename__ = "sandboxes"
    __table_args__ = (
        Index("ix_sandboxes_owner_status", "owner_id", "status"),
        Index("ix_sandboxes_expires_at", "expires_at"),
        Index(
            "uq_sandboxes_one_active_per_owner",
            "owner_id",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND status IN "
                "('creating', 'ready', 'busy', 'deleting')"
            ),
            sqlite_where=text(
                "deleted_at IS NULL AND status IN "
                "('creating', 'ready', 'busy', 'deleting')"
            ),
        ),
    )
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    project_source_id: Mapped[str | None] = mapped_column(ForeignKey("project_sources.id"))
    template_id: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    runtime_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_reason: Mapped[str | None] = mapped_column(String(200))


class SessionRow(TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_owner_status", "owner_id", "status"),)
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(ForeignKey("sandboxes.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    last_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    compacted_summary_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TurnRow(TimestampMixin, Base):
    __tablename__ = "turns"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    funding_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="owner_funded")
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="server-default")
    reasoning_effort: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalRow(TimestampMixin, Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(ForeignKey("sandboxes.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EventOffsetRow(Base):
    __tablename__ = "event_offsets"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    stream_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    last_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class ArtifactRow(TimestampMixin, Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(ForeignKey("sandboxes.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(1_000), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PreviewRow(TimestampMixin, Base):
    __tablename__ = "previews"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(ForeignKey("sandboxes.id"), nullable=False)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageLedgerRow(TimestampMixin, Base):
    __tablename__ = "usage_ledger"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    sandbox_id: Mapped[str | None] = mapped_column(ForeignKey("sandboxes.id"))
    turn_id: Mapped[str | None] = mapped_column(ForeignKey("turns.id"))
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    funding_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DailyQuotaCounterRow(Base):
    __tablename__ = "daily_quota_counters"
    __table_args__ = (
        UniqueConstraint("scope_key", "day", name="uq_daily_quota_scope_day"),
    )
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(220), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reserved_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuotaReservationRow(TimestampMixin, Base):
    __tablename__ = "quota_reservations"
    turn_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False)
    reserved_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    settled_cost_microusd: Mapped[int | None] = mapped_column(BigInteger)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSettingRow(Base):
    __tablename__ = "admin_settings"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CleanupJobRow(TimestampMixin, Base):
    __tablename__ = "cleanup_jobs"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    sandbox_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_code: Mapped[str | None] = mapped_column(String(200))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEventRow(TimestampMixin, Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(200), index=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(200), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    retention_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
