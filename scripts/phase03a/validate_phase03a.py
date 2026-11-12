from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / "storage" / "30_DATABASES" / "studio.db"
REPORT = ROOT / "storage" / "80_REPORTS" / "phase03a_validation.json"
IMPORT_REPORT = ROOT / "storage" / "80_REPORTS" / "phase03a_phase02_import.json"
BACKUP_REPORT = ROOT / "storage" / "80_REPORTS" / "phase03a_backup_recovery.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    connection = sqlite3.connect(DATABASE)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        counts = {
            "skills": connection.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
            "validation_reports": connection.execute("SELECT COUNT(*) FROM validation_reports").fetchone()[0],
            "import_batches": connection.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0],
            "import_records": connection.execute("SELECT COUNT(*) FROM import_records").fetchone()[0],
            "backups": connection.execute("SELECT COUNT(*) FROM backups").fetchone()[0],
        }
        enabled_skills = connection.execute("SELECT COUNT(*) FROM skills WHERE enabled != 0").fetchone()[0]
        report_hashes = {
            row[0]: row[1] for row in connection.execute("SELECT report_path,report_sha256 FROM validation_reports")
        }
        source_hashes_match = all(
            Path(path).is_file() and sha256(Path(path)) == digest for path, digest in report_hashes.items()
        )
        unknown_paths = [
            Path(row[0])
            for row in connection.execute(
                "SELECT unknown_fields_path FROM import_batches WHERE unknown_fields_path IS NOT NULL"
            )
        ]
    finally:
        connection.close()
    import_report = json.loads(IMPORT_REPORT.read_text(encoding="utf-8"))
    backup_report = json.loads(BACKUP_REPORT.read_text(encoding="utf-8"))
    required_tables = {
        "character_variants",
        "import_batches",
        "import_records",
        "users",
        "app_settings",
    }
    required_triggers = {
        "prevent_approvals_update",
        "prevent_approvals_delete",
        "prevent_audit_events_update",
        "prevent_audit_events_delete",
        "prevent_approved_asset_versions_update",
        "prevent_approved_asset_versions_delete",
    }
    checks = {
        "database_integrity": integrity == "ok",
        "migration_head": revision in {
            "0004_phase03a_foundation", "0005_agent_skills_registry", "0006_registry_snapshot_guards",
        },
        "required_tables": required_tables <= tables and len(tables) == {
            "0004_phase03a_foundation": 31, "0005_agent_skills_registry": 35,
            "0006_registry_snapshot_guards": 35,
        }.get(revision),
        "required_triggers": required_triggers <= triggers,
        "phase02_skills_imported_disabled": counts["skills"] == 14 and enabled_skills == 0,
        "phase02_reports_imported": counts["validation_reports"] == 4,
        "import_provenance_complete": counts["import_records"] == 18,
        "source_hashes_match": source_hashes_match,
        "unknown_field_evidence_present": bool(unknown_paths) and all(path.is_file() for path in unknown_paths),
        "import_report_passed": import_report["status"] == "PASS",
        "backup_recovery_passed": backup_report["status"] == "PASS" and counts["backups"] >= 1,
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": "PHASE_03A_LOCAL_APPLICATION_FOUNDATION",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "database": {
            "path": str(DATABASE),
            "integrity_check": integrity,
            "migration_revision": revision,
            "table_count": len(tables),
            "counts": counts,
        },
    }
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
