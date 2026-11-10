"""Create a new, timestamped backup of durable managed zones (never overwrites or deletes).

- studio.db is copied with the SQLite online backup API and integrity-checked.
- Approved masters, published outputs and reports are copied file by file.
- Every copied file gets a SHA-256 entry in backup_manifest.json inside the new folder.
Regenerable zones (10_DEVELOPMENT, 20_TEMP) and the backups folder itself are excluded.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "storage" / "30_DATABASES" / "studio.db"
ZONES = ["storage/40_APPROVED_MASTERS", "storage/50_PUBLISHED_OUTPUTS", "storage/80_REPORTS"]
SKIP_SUFFIXES = ("-wal", "-shm")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = ROOT / "storage" / "60_BACKUPS" / "managed" / stamp
    if target.exists():
        print(f"refusing to reuse existing backup folder: {target}")
        return 1
    target.mkdir(parents=True)
    entries = []

    if DB.exists():
        db_copy = target / "studio.db"
        with sqlite3.connect(DB.as_posix()) as source, sqlite3.connect(db_copy.as_posix()) as dest:
            source.backup(dest)
        with sqlite3.connect(f"file:{db_copy.as_posix()}?mode=ro", uri=True) as check:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            print(f"database copy failed integrity: {integrity}")
            return 1
        entries.append({"path": "studio.db", "sha256": sha256(db_copy), "bytes": db_copy.stat().st_size,
                        "source": "storage/30_DATABASES/studio.db (online backup API)"})

    for zone in ZONES:
        base = ROOT / zone
        if not base.exists():
            continue
        for source_file in sorted(p for p in base.rglob("*") if p.is_file()):
            if source_file.name == ".gitkeep" or source_file.name.endswith(SKIP_SUFFIXES):
                continue
            relative = source_file.relative_to(ROOT / "storage")
            destination = target / "zones" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
            entries.append({"path": f"zones/{relative.as_posix()}", "sha256": sha256(destination),
                            "bytes": destination.stat().st_size, "source": relative.as_posix()})

    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "backup_folder": str(target),
                "file_count": len(entries), "files": entries}
    (target / "backup_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
    print(f"backup written: {target} files={len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
