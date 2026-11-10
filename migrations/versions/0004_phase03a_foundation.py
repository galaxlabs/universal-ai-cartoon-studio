"""Add the Phase 03-A application foundation records."""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_phase03a_foundation"
down_revision: str | None = "0003_mcp_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE character_variants (
          id TEXT PRIMARY KEY,
          character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE RESTRICT,
          code TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT,
          config_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(character_id, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE import_batches (
          id TEXT PRIMARY KEY,
          source_kind TEXT NOT NULL,
          source_path TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          dry_run INTEGER NOT NULL DEFAULT 0 CHECK(dry_run IN (0,1)),
          counts_json TEXT NOT NULL DEFAULT '{}',
          unknown_fields_path TEXT,
          error_json TEXT,
          started_at TEXT NOT NULL,
          completed_at TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE import_records (
          id TEXT PRIMARY KEY,
          batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE RESTRICT,
          source_kind TEXT NOT NULL,
          source_key TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          target_kind TEXT NOT NULL,
          target_id TEXT NOT NULL,
          target_fingerprint TEXT NOT NULL,
          imported_at TEXT NOT NULL,
          UNIQUE(source_kind, source_key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE users (
          id TEXT PRIMARY KEY,
          username TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          role TEXT NOT NULL,
          api_token_hash TEXT UNIQUE,
          active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE app_settings (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    op.create_index("idx_character_variants_character", "character_variants", ["character_id", "status"])
    op.create_index("idx_import_batches_source", "import_batches", ["source_kind", "started_at"])
    op.create_index("idx_import_records_target", "import_records", ["target_kind", "target_id"])
    op.create_index("idx_audit_events_subject_created", "audit_events", ["subject_kind", "subject_id", "created_at"])
    op.create_index("idx_backups_created", "backups", ["created_at"])
    op.execute(
        """
        CREATE TRIGGER prevent_approved_asset_versions_update
        BEFORE UPDATE ON asset_versions
        WHEN OLD.status IN ('APPROVED', 'PUBLISHED')
        BEGIN SELECT RAISE(ABORT, 'approved asset versions are immutable'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_approved_asset_versions_delete
        BEFORE DELETE ON asset_versions
        WHEN OLD.status IN ('APPROVED', 'PUBLISHED')
        BEGIN SELECT RAISE(ABORT, 'approved asset versions are immutable'); END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_approved_asset_versions_delete")
    op.execute("DROP TRIGGER IF EXISTS prevent_approved_asset_versions_update")
    op.drop_index("idx_backups_created", table_name="backups")
    op.drop_index("idx_audit_events_subject_created", table_name="audit_events")
    op.drop_index("idx_import_records_target", table_name="import_records")
    op.drop_index("idx_import_batches_source", table_name="import_batches")
    op.drop_index("idx_character_variants_character", table_name="character_variants")
    op.drop_table("app_settings")
    op.drop_table("users")
    op.drop_table("import_records")
    op.drop_table("import_batches")
    op.drop_table("character_variants")
