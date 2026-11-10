"""Protect evidence tables with append-only database triggers."""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_append_only_evidence"
down_revision: str | None = "0001_phase0_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("job_events", "approvals", "audit_events")


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER prevent_{table}_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER prevent_{table}_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_delete")
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_update")
