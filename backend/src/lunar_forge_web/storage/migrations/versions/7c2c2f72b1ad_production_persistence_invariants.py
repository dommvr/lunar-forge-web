"""production persistence invariants

Revision ID: 7c2c2f72b1ad
Revises: 1b13400551fd
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


revision: str = "7c2c2f72b1ad"
down_revision: Union[str, Sequence[str], None] = "1b13400551fd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ACTIVE_SANDBOX_SQL = (
    "deleted_at IS NULL AND status IN ('creating', 'ready', 'busy', 'deleting')"
)


def _retention_expression() -> str:
    if op.get_bind().dialect.name == "postgresql":
        return "created_at + interval '30 days'"
    return "datetime(created_at, '+30 days')"


def upgrade() -> None:
    admin_settings = sa.table(
        "admin_settings",
        sa.column("key", sa.String(length=200)),
        sa.column("value", sa.JSON()),
    )
    seed_values = [
        {"key": "sandbox_kill_switch_enabled", "value": {"enabled": False}},
        {"key": "owner_funded_enabled", "value": {"enabled": True}},
    ]
    insert = (
        postgresql_insert(admin_settings)
        if op.get_bind().dialect.name == "postgresql"
        else sqlite_insert(admin_settings)
    )
    op.execute(
        insert.values(seed_values).on_conflict_do_nothing(index_elements=["key"])
    )
    op.add_column("invites", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column("project_sources", sa.Column("deleted_at", sa.DateTime(timezone=True)))

    op.add_column("sandboxes", sa.Column("retention_expires_at", sa.DateTime(timezone=True)))
    op.add_column("sandboxes", sa.Column("deletion_reason", sa.String(length=200)))
    op.create_index("ix_sandboxes_expires_at", "sandboxes", ["expires_at"])
    op.create_index(
        "uq_sandboxes_one_active_per_owner",
        "sandboxes",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_SANDBOX_SQL),
        sqlite_where=sa.text(_ACTIVE_SANDBOX_SQL),
    )

    op.add_column("sessions", sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.add_column("sessions", sa.Column("retention_expires_at", sa.DateTime(timezone=True)))

    op.add_column(
        "turns",
        sa.Column(
            "funding_mode",
            sa.String(length=32),
            nullable=False,
            server_default="owner_funded",
        ),
    )
    op.add_column(
        "turns",
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="openai"),
    )
    op.add_column(
        "turns",
        sa.Column(
            "model", sa.String(length=200), nullable=False, server_default="server-default"
        ),
    )
    op.add_column(
        "turns",
        sa.Column(
            "reasoning_effort", sa.String(length=32), nullable=False, server_default="medium"
        ),
    )
    op.add_column(
        "turns",
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "turns",
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "turns",
        sa.Column(
            "estimated_cost_microusd", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column("turns", sa.Column("error_code", sa.String(length=200)))
    op.add_column("turns", sa.Column("retention_expires_at", sa.DateTime(timezone=True)))
    op.add_column("approvals", sa.Column("retention_expires_at", sa.DateTime(timezone=True)))
    op.add_column("artifacts", sa.Column("downloaded_at", sa.DateTime(timezone=True)))

    op.add_column(
        "usage_ledger",
        sa.Column("day", sa.String(length=10), nullable=False, server_default="1970-01-01"),
    )
    op.add_column(
        "usage_ledger",
        sa.Column(
            "funding_mode", sa.String(length=32), nullable=False, server_default="owner_funded"
        ),
    )
    op.add_column(
        "usage_ledger",
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="openai"),
    )
    op.add_column(
        "usage_ledger",
        sa.Column(
            "model", sa.String(length=200), nullable=False, server_default="server-default"
        ),
    )
    op.add_column(
        "usage_ledger", sa.Column("retention_expires_at", sa.DateTime(timezone=True))
    )
    op.execute(
        sa.text(
            "UPDATE usage_ledger SET day = substr(CAST(created_at AS VARCHAR), 1, 10), "
            f"retention_expires_at = {_retention_expression()}"
        )
    )
    with op.batch_alter_table("usage_ledger") as batch:
        batch.alter_column("retention_expires_at", nullable=False)
    op.create_index("ix_usage_ledger_user_day", "usage_ledger", ["user_id", "day"])
    op.create_index("ix_usage_ledger_retention", "usage_ledger", ["retention_expires_at"])

    op.add_column("daily_quota_counters", sa.Column("scope_key", sa.String(length=220)))
    op.add_column(
        "daily_quota_counters",
        sa.Column("reserved_cost_microusd", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "daily_quota_counters",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(sa.text("UPDATE daily_quota_counters SET scope_key = 'user:' || user_id"))
    with op.batch_alter_table("daily_quota_counters") as batch:
        batch.drop_constraint("uq_daily_quota_user_day", type_="unique")
        batch.alter_column("scope_key", nullable=False)
        batch.alter_column("user_id", existing_type=sa.String(length=200), nullable=True)
        batch.create_unique_constraint(
            "uq_daily_quota_scope_day", ["scope_key", "day"]
        )

    op.create_table(
        "quota_reservations",
        sa.Column("turn_id", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.String(length=200), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("reserved_cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settled_cost_microusd", sa.BigInteger()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("turn_id"),
    )

    op.add_column(
        "cleanup_jobs", sa.Column("retention_expires_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "audit_events", sa.Column("retention_expires_at", sa.DateTime(timezone=True))
    )
    op.execute(
        sa.text(
            "UPDATE audit_events SET retention_expires_at = "
            f"{_retention_expression()}"
        )
    )
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("retention_expires_at", nullable=False)
    op.create_index("ix_audit_events_retention", "audit_events", ["retention_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_retention", table_name="audit_events")
    op.drop_column("audit_events", "retention_expires_at")
    op.drop_column("cleanup_jobs", "retention_expires_at")
    op.drop_table("quota_reservations")

    op.execute(sa.text("DELETE FROM daily_quota_counters WHERE user_id IS NULL"))
    with op.batch_alter_table("daily_quota_counters") as batch:
        batch.drop_constraint("uq_daily_quota_scope_day", type_="unique")
        batch.alter_column("user_id", existing_type=sa.String(length=200), nullable=False)
        batch.create_unique_constraint(
            "uq_daily_quota_user_day", ["user_id", "day"]
        )
    op.drop_column("daily_quota_counters", "updated_at")
    op.drop_column("daily_quota_counters", "reserved_cost_microusd")
    op.drop_column("daily_quota_counters", "scope_key")

    op.drop_index("ix_usage_ledger_retention", table_name="usage_ledger")
    op.drop_index("ix_usage_ledger_user_day", table_name="usage_ledger")
    op.drop_column("usage_ledger", "retention_expires_at")
    op.drop_column("usage_ledger", "model")
    op.drop_column("usage_ledger", "provider")
    op.drop_column("usage_ledger", "funding_mode")
    op.drop_column("usage_ledger", "day")

    op.drop_column("artifacts", "downloaded_at")
    op.drop_column("approvals", "retention_expires_at")
    op.drop_column("turns", "retention_expires_at")
    op.drop_column("turns", "error_code")
    op.drop_column("turns", "estimated_cost_microusd")
    op.drop_column("turns", "output_tokens")
    op.drop_column("turns", "input_tokens")
    op.drop_column("turns", "reasoning_effort")
    op.drop_column("turns", "model")
    op.drop_column("turns", "provider")
    op.drop_column("turns", "funding_mode")
    op.drop_column("sessions", "retention_expires_at")
    op.drop_column("sessions", "closed_at")
    op.drop_index("uq_sandboxes_one_active_per_owner", table_name="sandboxes")
    op.drop_index("ix_sandboxes_expires_at", table_name="sandboxes")
    op.drop_column("sandboxes", "deletion_reason")
    op.drop_column("sandboxes", "retention_expires_at")
    op.drop_column("project_sources", "deleted_at")
    op.drop_column("invites", "accepted_at")
    op.execute(
        sa.text(
            "DELETE FROM admin_settings WHERE key IN "
            "('sandbox_kill_switch_enabled', 'owner_funded_enabled')"
        )
    )
