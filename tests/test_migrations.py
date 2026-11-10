from __future__ import annotations

import sqlite3
from pathlib import Path

from studio_manager.database import downgrade_database, upgrade_database


def user_tables(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        return {row[0] for row in connection.execute(query)}
    finally:
        connection.close()


def test_upgrade_downgrade_and_reupgrade(database_path: Path) -> None:
    upgrade_database(database_path)
    upgraded = user_tables(database_path)
    assert "projects" in upgraded
    assert "production_jobs" in upgraded
    assert "alembic_version" in upgraded
    assert len(upgraded) == 31
    assert {"character_variants", "import_batches", "import_records", "users", "app_settings"} <= upgraded

    downgrade_database(database_path)
    assert user_tables(database_path) == {"alembic_version"}

    upgrade_database(database_path)
    assert len(user_tables(database_path)) == 31


def test_phase03a_forward_migration_preserves_phase02_evidence(database_path: Path) -> None:
    upgrade_database(database_path, "0003_mcp_gateway")
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            "INSERT INTO approvals(id,subject_kind,subject_id,decision,decided_by,created_at) "
            "VALUES('apr_preserved','MCP_OPERATION','probe','APPROVED','test','2026-11-01T00:00:00+00:00')"
        )
        connection.execute(
            "INSERT INTO audit_events(actor,action,subject_kind,subject_id,created_at) "
            "VALUES('test','CREATE','PROBE','probe','2026-11-01T00:00:00+00:00')"
        )
        connection.commit()
    finally:
        connection.close()

    upgrade_database(database_path)
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT decision FROM approvals WHERE id='apr_preserved'").fetchone()[0] == "APPROVED"
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()

    downgrade_database(database_path, "0003_mcp_gateway")
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM approvals WHERE id='apr_preserved'").fetchone()[0] == 1
        assert len(user_tables(database_path)) == 26
    finally:
        connection.close()

    upgrade_database(database_path)
    assert len(user_tables(database_path)) == 31
