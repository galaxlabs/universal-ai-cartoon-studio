from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.config import PROJECT_ROOT  # noqa: E402
from studio_manager.database import create_database_engine, upgrade_database  # noqa: E402
from studio_manager.import_service import Phase02ImportService  # noqa: E402
from studio_manager.storage_service import LocalStorageService  # noqa: E402

DATABASE = ROOT / "storage" / "30_DATABASES" / "studio.db"
REPORT = ROOT / "storage" / "80_REPORTS" / "phase03a_phase02_import.json"
SOURCES = [
    ("PHASE02_SKILLS", ROOT / "config" / "phase02.skills.json"),
    ("PHASE02_REPORT", ROOT / "storage" / "80_REPORTS" / "phase02_validation.json"),
    ("PHASE02_REPORT", ROOT / "storage" / "80_REPORTS" / "phase02_unreal_mcp_integration.json"),
    ("PHASE02_REPORT", ROOT / "storage" / "80_REPORTS" / "phase02_integration_baseline.json"),
    ("PHASE02_REPORT", ROOT / "storage" / "80_REPORTS" / "phase02_blender_mcp_integration.json"),
]


def main() -> int:
    if ROOT != PROJECT_ROOT:
        raise RuntimeError("project root mismatch")
    upgrade_database(DATABASE)
    engine = create_database_engine(DATABASE)
    importer = Phase02ImportService(engine, LocalStorageService(ROOT / "storage" / "80_REPORTS"))
    results: list[dict[str, object]] = []
    for source_kind, path in SOURCES:
        dry_run = importer.run(source_kind, str(path), dry_run=True, actor="phase03a-migration")
        imported = importer.run(source_kind, str(path), dry_run=False, actor="phase03a-migration")
        repeated = importer.run(source_kind, str(path), dry_run=False, actor="phase03a-migration")
        results.append(
            {
                "source": str(path),
                "source_kind": source_kind,
                "dry_run": dry_run,
                "imported": imported,
                "repeated": repeated,
            }
        )
    connection = sqlite3.connect(DATABASE)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        counts = {
            "skills": connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
            "validation_reports": connection.execute("SELECT COUNT(*) FROM validation_reports").fetchone()[0],
            "import_batches": connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0],
            "import_records": connection.execute("SELECT COUNT(*) FROM import_records").fetchone()[0],
        }
    finally:
        connection.close()
        engine.dispose()
    status = "PASS" if integrity == "ok" and revision in {
        "0004_phase03a_foundation", "0005_agent_skills_registry",
    } else "FAIL"
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": "PHASE_03A_PHASE02_RECORD_IMPORT",
        "status": status,
        "database": str(DATABASE),
        "integrity_check": integrity,
        "migration_revision": revision,
        "counts": counts,
        "sources": results,
    }
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)
    print(json.dumps(report))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
