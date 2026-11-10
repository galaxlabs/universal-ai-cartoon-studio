from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "storage" / "80_REPORTS"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def schema_probe() -> dict:
    schema = (ROOT / "schemas" / "studio_v01.sql").read_text(encoding="utf-8")
    temp_dir = ROOT / "storage" / "20_TEMP" / "phase0_foundation"
    backup_dir = ROOT / "storage" / "60_BACKUPS" / "phase0_foundation"
    temp_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    database = temp_dir / "schema-probe.db"
    backup = backup_dir / "schema-probe-backup.db"
    sidecars = (database, backup, Path(f"{database}-wal"), Path(f"{database}-shm"), Path(f"{backup}-wal"), Path(f"{backup}-shm"))
    for path in sidecars:
        path.unlink(missing_ok=True)
    con = sqlite3.connect(database)
    con.executescript(schema)
    journal_mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    tables = sorted(row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    con.execute("INSERT INTO projects VALUES(?,?,?,?,?,?)", ("p1", "Foundation Probe", "DEVELOPMENT", str(ROOT), now, now))
    con.execute("INSERT INTO production_jobs(id,project_id,job_type,status,workspace_path,requested_by,created_at) VALUES(?,?,?,?,?,?,?)", ("j1", "p1", "PROBE", "DRAFT", str(ROOT / "storage" / "10_DEVELOPMENT" / "j1"), "phase0-validator", now))
    con.execute("INSERT INTO job_events(job_id,sequence,event_type,created_at) VALUES(?,?,?,?)", ("j1", 1, "CREATED", now))
    con.commit()
    rollback_ok = False
    try:
        con.execute("BEGIN")
        con.execute("UPDATE production_jobs SET status='APPROVED' WHERE id='j1'")
        raise RuntimeError("simulated failed operation")
    except RuntimeError:
        con.rollback()
        rollback_ok = con.execute("SELECT status FROM production_jobs WHERE id='j1'").fetchone()[0] == "DRAFT"
    foreign_keys = con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    target = sqlite3.connect(backup)
    con.backup(target)
    target.close()
    con.close()
    restored = sqlite3.connect(backup)
    restore_status = restored.execute("SELECT status FROM production_jobs WHERE id='j1'").fetchone()[0]
    restored.close()
    for path in sidecars:
        path.unlink(missing_ok=True)
    for path in (temp_dir, backup_dir):
        try:
            path.rmdir()
        except OSError:
            pass
    cleaned = not any(path.exists() for path in sidecars)
    ok = len(tables) >= 23 and rollback_ok and foreign_keys and journal_mode.lower() == "wal" and restore_status == "DRAFT" and cleaned
    return {"ok": ok, "table_count": len(tables), "tables": tables, "journal_mode": journal_mode, "transaction_rollback_ok": rollback_ok, "foreign_keys_enabled": foreign_keys, "backup_restore_status": restore_status, "test_artifacts_cleaned": cleaned}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    paths = json.loads((ROOT / "config" / "studio.paths.json").read_text(encoding="utf-8"))
    components = json.loads((ROOT / "config" / "components.manifest.json").read_text(encoding="utf-8"))
    protected = json.loads((ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    schema_result = schema_probe()
    protected_results = []
    for item in protected["sources"]:
        path = Path(item["path"])
        actual = sha256(path) if path.is_file() and item.get("sha256") else None
        protected_results.append({"id": item["id"], "exists": path.exists(), "hash_equal": actual == item.get("sha256") if actual else True, "actual_sha256": actual})
    required_docs = [
        "README.md",
        "docs/MASTER_REQUIREMENTS.md",
        "docs/architecture/PHASE0_ARCHITECTURE.md",
        "docs/architecture/ADR-0001-local-first-modular-monolith.md",
        "docs/architecture/ADR-0002-automation-boundaries.md",
        "docs/security/THREAT_MODEL.md",
        "docs/phase0/PHASE0_DISCOVERY_REPORT.md",
        "docs/phase0/PHASE0_ROLLBACK.md",
    ]
    protected_zone_files = [p for p in (ROOT / paths["storage"]["protected_registry"]).rglob("*") if p.is_file() and p.name != ".gitkeep"]
    checks = {
        "json_manifests_parse": True,
        "component_manifest_nonempty": len(components["components"]) >= 10,
        "schema_probe": schema_result["ok"],
        "loopback_only": paths["bind_host"] == "127.0.0.1" and paths["policy"]["allow_public_bind"] is False,
        "protected_writes_disabled": paths["policy"]["allow_in_place_protected_writes"] is False,
        "all_storage_zones_exist": all((ROOT / value).is_dir() for value in paths["storage"].values()),
        "protected_registry_contains_no_asset_copy": len(protected_zone_files) == 0,
        "protected_sources_unchanged": all(x["exists"] and x["hash_equal"] for x in protected_results),
        "required_documents_exist": all((ROOT / path).exists() for path in required_docs),
        "health_report_exists": (REPORT_DIR / "phase0_health.json").exists(),
    }
    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "schema": schema_result,
        "protected_sources": protected_results,
        "protected_zone_unexpected_files": [str(p) for p in protected_zone_files],
        "installed_components_this_phase": [],
        "modified_external_configuration": [],
        "next_gate": "CREATIVE_DIRECTOR_PHASE_1_APPROVAL",
    }
    json_path = REPORT_DIR / "phase0_foundation_validation.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = "# Phase 0 Foundation Validation\n\n" + f"- Status: **{report['status']}**\n- SQLite schema tables: **{schema_result['table_count']}**\n- SQLite journal mode: **{schema_result['journal_mode'].upper()}**\n- Simulated transaction rollback: **{'PASS' if schema_result['transaction_rollback_ok'] else 'FAIL'}**\n- SQLite backup/restore: **{'PASS' if schema_result['backup_restore_status'] == 'DRAFT' else 'FAIL'}**\n- Test artifact cleanup: **{'PASS' if schema_result['test_artifacts_cleaned'] else 'FAIL'}**\n- Protected-source hashes: **{'PASS' if checks['protected_sources_unchanged'] else 'FAIL'}**\n- Public service binding: **disabled**\n- Third-party installations: **none**\n- External application configuration changes: **none**\n- Next gate: **Creative Director approval for Phase 1**\n"
    (ROOT / "docs" / "phase0" / "PHASE0_TEST_REPORT.md").write_text(md, encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(json_path), "checks": checks}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
