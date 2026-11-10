"""Create the approved Phase 0 foundation schema."""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001_phase0_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_IN_CREATION_ORDER = [
    "projects", "series", "episodes", "scenes", "shots", "characters", "assets", "asset_versions",
    "character_versions", "files", "dependencies", "agents", "mcp_servers", "skills", "capabilities",
    "production_jobs", "job_events", "validation_reports", "approvals", "change_requests", "backups",
    "components", "audit_events",
]


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "studio_v01.sql"
    schema = schema_path.read_text(encoding="utf-8")
    statements = [statement.strip() for statement in schema.split(";") if statement.strip()]
    for statement in statements:
        if not statement.upper().startswith("PRAGMA"):
            op.execute(statement)


def downgrade() -> None:
    connection = op.get_bind()
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    for table in reversed(TABLES_IN_CREATION_ORDER):
        op.drop_table(table)
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
