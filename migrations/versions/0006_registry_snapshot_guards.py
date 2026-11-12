"""Close SQLite REPLACE conflicts without rewriting the already-issued0005 revision."""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_registry_snapshot_guards"
down_revision: str | None = "0005_agent_skills_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BEFORE INSERT runs before REPLACE's implicit deletion, even when recursive
    # delete triggers are OFF. Protect both independent uniqueness conflicts.
    #0005 already treats DRAFT versions as immutable snapshots too; edits create
    # another version rather than replacing an existing version in any state.
    op.execute("""
        CREATE TRIGGER prevent_studio_agent_versions_insert
        BEFORE INSERT ON studio_agent_versions
        WHEN EXISTS (
          SELECT 1 FROM studio_agent_versions
          WHERE id = NEW.id OR (agent_id = NEW.agent_id AND version = NEW.version)
        )
        BEGIN SELECT RAISE(ABORT, 'registry version snapshots are immutable'); END
    """)
    op.execute("""
        CREATE TRIGGER prevent_studio_skill_versions_insert
        BEFORE INSERT ON studio_skill_versions
        WHEN EXISTS (
          SELECT 1 FROM studio_skill_versions
          WHERE id = NEW.id OR (skill_id = NEW.skill_id AND version = NEW.version)
        )
        BEGIN SELECT RAISE(ABORT, 'registry version snapshots are immutable'); END
    """)


def downgrade() -> None:
    # Explicit rollback restores0005's original guards, including its known
    # replacement vulnerability. Never downgrade production as an M2 remedy.
    op.execute("DROP TRIGGER prevent_studio_skill_versions_insert")
    op.execute("DROP TRIGGER prevent_studio_agent_versions_insert")
