"""Read-only registry validation; an explicit database path is mandatory."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def validate(path: Path) -> dict:
    connection = sqlite3.connect(path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        tables = {r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        triggers = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    finally:
        connection.close()
    registry_tables = {"studio_agents", "studio_skills", "studio_agent_versions", "studio_skill_versions"}
    required_triggers = {
        f"prevent_{table}_{action}" for table in ("studio_agent_versions", "studio_skill_versions")
        for action in ("insert", "update", "delete")
    }
    checks = {
        "head": revision == "0006_registry_snapshot_guards",
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "registry_tables": registry_tables <= tables and len(tables) == 35,
        "snapshot_guards": required_triggers <= triggers,
        "legacy_tables_preserved": {"agents", "skills", "capabilities", "audit_events"} <= tables,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "revision": revision,
            "table_count": len(tables), "checks": checks, "read_only": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Use a disposable test/copy database")
    args = parser.parse_args()
    result = validate(args.database)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
