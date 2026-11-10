"""Add persistent policy and invocation evidence for the MCP gateway."""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_mcp_gateway"
down_revision: str | None = "0002_append_only_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE mcp_gateway_policies (
          server_id TEXT PRIMARY KEY REFERENCES mcp_servers(id) ON DELETE CASCADE,
          application TEXT NOT NULL,
          operation_selector TEXT NOT NULL,
          allowed_operations_json TEXT NOT NULL,
          denied_operations_json TEXT NOT NULL,
          write_operations_json TEXT NOT NULL,
          approval_operations_json TEXT NOT NULL,
          write_scopes_json TEXT NOT NULL,
          timeout_seconds INTEGER NOT NULL,
          max_concurrency INTEGER NOT NULL,
          retry_limit INTEGER NOT NULL,
          rollback_strategy TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE mcp_invocations (
          id TEXT PRIMARY KEY,
          server_id TEXT NOT NULL REFERENCES mcp_servers(id),
          operation TEXT NOT NULL,
          arguments_json TEXT NOT NULL,
          workspace_path TEXT,
          approval_id TEXT REFERENCES approvals(id),
          status TEXT NOT NULL,
          attempt_count INTEGER NOT NULL DEFAULT 0,
          duration_ms INTEGER,
          result_summary_json TEXT,
          rollback_status TEXT,
          error_code TEXT,
          actor TEXT NOT NULL,
          created_at TEXT NOT NULL,
          completed_at TEXT
        )
        """
    )
    op.create_index("idx_mcp_invocations_server_status", "mcp_invocations", ["server_id", "status"])
    op.create_index("idx_mcp_invocations_created", "mcp_invocations", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_mcp_invocations_created", table_name="mcp_invocations")
    op.drop_index("idx_mcp_invocations_server_status", table_name="mcp_invocations")
    op.drop_table("mcp_invocations")
    op.drop_table("mcp_gateway_policies")
