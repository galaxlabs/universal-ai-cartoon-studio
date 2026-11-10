from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.backup_service import BackupService  # noqa: E402
from studio_manager.database import create_database_engine  # noqa: E402

DATABASE = ROOT / "storage" / "30_DATABASES" / "studio.db"
BACKUP_ROOT = ROOT / "storage" / "60_BACKUPS" / "phase03a"
RECOVERY_ROOT = ROOT / "storage" / "20_TEMP" / "recovery"
REPORT = ROOT / "storage" / "80_REPORTS" / "phase03a_backup_recovery.json"


def main() -> int:
    engine = create_database_engine(DATABASE)
    service = BackupService(engine, DATABASE, BACKUP_ROOT, RECOVERY_ROOT)
    backup = service.create(actor="phase03a-verifier")
    destination = RECOVERY_ROOT / f"restore-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}.db"
    restored = service.restore_copy(Path(str(backup["path"])), destination)
    cleaned = [destination, Path(f"{destination}-wal"), Path(f"{destination}-shm")]
    for path in cleaned:
        path.unlink(missing_ok=True)
    engine.dispose()
    passed = (
        backup["integrity_check"] == "ok"
        and restored["integrity_check"] == "ok"
        and backup["sha256"] == restored["sha256"]
        and not any(path.exists() for path in cleaned)
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": "PHASE_03A_BACKUP_RECOVERY",
        "status": "PASS" if passed else "FAIL",
        "backup": backup,
        "restored_copy": restored,
        "recovery_copy_cleaned": not any(path.exists() for path in cleaned),
        "live_database_replaced": False,
    }
    temporary = REPORT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REPORT)
    print(json.dumps(report))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
