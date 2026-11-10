"""Read-only Phase 03-B entry checks from docs/phase03a/PHASE03B_HANDOFF.md.

This script does NOT approve Phase 03-B. It reports whether the technical entry
conditions hold; explicit Creative Director approval is still required separately.
Writes storage/80_REPORTS/phase03b_entry_check.json.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "storage" / "80_REPORTS"
DB = ROOT / "storage" / "30_DATABASES" / "studio.db"
EXPECTED_REVISION = "0004_phase03a_foundation"


def check_revision() -> dict[str, object]:
    if not DB.exists():
        return {"pass": False, "detail": "database missing"}
    with sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True) as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    ok = bool(revision) and revision[0] == EXPECTED_REVISION and integrity == "ok"
    return {"pass": ok, "detail": {"revision": revision[0] if revision else None, "integrity": integrity}}


def check_validation() -> dict[str, object]:
    path = REPORTS / "phase03a_validation.json"
    if not path.exists():
        return {"pass": False, "detail": "phase03a_validation.json missing"}
    status = json.loads(path.read_text(encoding="utf-8")).get("status")
    return {"pass": status == "PASS", "detail": {"status": status}}


def check_backup() -> dict[str, object]:
    backup_dir = ROOT / "storage" / "60_BACKUPS" / "phase03a"
    backups = sorted(p for p in backup_dir.glob("studio-*.db")) if backup_dir.exists() else []
    if not backups:
        return {"pass": False, "detail": "no Phase 03-A backup found"}
    latest = backups[-1]
    with sqlite3.connect(f"file:{latest.as_posix()}?mode=ro", uri=True) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    return {"pass": integrity == "ok", "detail": {"latest": latest.name, "integrity": integrity}}


def check_protected_sources() -> dict[str, object]:
    import hashlib

    config = json.loads((ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    results = {}
    for source in config["sources"]:
        if "sha256" not in source:
            continue
        path = Path(source["path"])
        if not path.exists():
            results[source["id"]] = "NOT_ACCESSIBLE_FROM_THIS_HOST"
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        results[source["id"]] = "MATCH" if digest == source["sha256"] else "MISMATCH"
    ok = all(value == "MATCH" for value in results.values())
    return {"pass": ok, "detail": results}


def main() -> int:
    checks = {
        "live_revision_and_integrity": check_revision(),
        "phase03a_validation_pass": check_validation(),
        "fresh_backup_integrity": check_backup(),
        "protected_source_hashes": check_protected_sources(),
    }
    technical_ready = all(c["pass"] for c in checks.values())
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "technical_entry_ready": technical_ready,
              "creative_director_approval": "REQUIRED_NOT_GRANTED_BY_THIS_SCRIPT"}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase03b_entry_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    print(json.dumps({k: v["pass"] for k, v in checks.items()}, indent=2))
    print(f"technical_entry_ready={technical_ready}")
    return 0 if technical_ready else 1


if __name__ == "__main__":
    sys.exit(main())
