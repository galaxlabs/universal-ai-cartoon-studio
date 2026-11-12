"""Add inert, versioned studio registries without changing imported legacy records."""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_agent_skills_registry"
down_revision: str | None = "0004_phase03a_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE studio_agents (
          id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          role TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE studio_agent_versions (
          id TEXT PRIMARY KEY,
          agent_id TEXT NOT NULL REFERENCES studio_agents(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL CHECK(version >= 1), instruction TEXT NOT NULL,
          model_profile TEXT NOT NULL DEFAULT '', allowed_tools_json TEXT NOT NULL DEFAULT '[]',
          allowed_skills_json TEXT NOT NULL DEFAULT '[]', config_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','APPROVED','RETIRED')),
          created_at TEXT NOT NULL, UNIQUE(agent_id,version)
        )
    """)
    op.execute("""
        CREATE TABLE studio_skills (
          id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)), created_at TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE studio_skill_versions (
          id TEXT PRIMARY KEY,
          skill_id TEXT NOT NULL REFERENCES studio_skills(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL CHECK(version >= 1), instructions TEXT NOT NULL,
          input_schema_json TEXT NOT NULL DEFAULT '{}', output_schema_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','APPROVED','RETIRED')),
          created_at TEXT NOT NULL, UNIQUE(skill_id,version)
        )
    """)
    # Even draft versions are snapshots: edits create another version. Approval,
    # retirement and enablement need a separate future lifecycle, not row mutation.
    for table in ("studio_agent_versions", "studio_skill_versions"):
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER prevent_{table}_{action.lower()} BEFORE {action} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'registry version snapshots are immutable'); END"
            )


def downgrade() -> None:
    for table in ("studio_agent_versions", "studio_skill_versions"):
        for action in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_{action}")
    for table in ("studio_skill_versions", "studio_skills", "studio_agent_versions", "studio_agents"):
        op.drop_table(table)
