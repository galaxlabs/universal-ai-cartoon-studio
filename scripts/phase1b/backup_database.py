from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "storage" / "30_DATABASES" / "studio.db"
BACKUP_DIR = ROOT / "storage" / "60_BACKUPS" / "phase1b"
REPORT = ROOT / "storage" / "80_REPORTS" / "phase1b_pre_migration_backup.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Studio database does not exist: {SOURCE}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    destination = BACKUP_DIR / f"studio-pre-phase1b-{timestamp}.db"
    source = sqlite3.connect(SOURCE)
    target = sqlite3.connect(destination)
    source.backup(target)
    target.close()
    source.close()
    restored = sqlite3.connect(destination)
    integrity = restored.execute("PRAGMA integrity_check").fetchone()[0]
    migration = restored.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    restored.close()
    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "source": str(SOURCE),
        "backup": str(destination),
        "sha256": sha256(destination),
        "bytes": destination.stat().st_size,
        "integrity_check": integrity,
        "migration_revision": migration,
        "restore_open_test": "PASS" if integrity == "ok" else "FAIL",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if integrity == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
