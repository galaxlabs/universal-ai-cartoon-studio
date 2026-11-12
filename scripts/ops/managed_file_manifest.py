"""Build a SHA-256 manifest for durable managed zones (read-only; writes only the manifest).

Covers backups, approved masters, published outputs, reports and database files that the
SQLite backup does not include. Regenerable zones (10_DEVELOPMENT, 20_TEMP) are excluded.
Usage: python scripts/ops/managed_file_manifest.py [--verify MANIFEST]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ZONES = ["storage/30_DATABASES", "storage/40_APPROVED_MASTERS", "storage/50_PUBLISHED_OUTPUTS",
         "storage/60_BACKUPS", "storage/80_REPORTS"]
EXCLUDE_SUFFIXES = (".db-wal", ".db-shm", ".tmp-wal", ".tmp-shm")
DEFAULT_OUT = ROOT / "storage" / "80_REPORTS" / "managed_file_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect() -> list[dict[str, object]]:
    entries = []
    for zone in ZONES:
        base = ROOT / zone
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if path.name.endswith(EXCLUDE_SUFFIXES) or path.name == ".gitkeep":
                continue
            entries.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                            "sha256": sha256(path)})
    return entries


def verify(manifest_path: Path) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    for entry in data["files"]:
        target = ROOT / entry["path"]
        if not target.exists():
            failures.append(f"MISSING {entry['path']}")
        elif sha256(target) != entry["sha256"]:
            failures.append(f"CHANGED {entry['path']}")
    print(f"checked={len(data['files'])} failures={len(failures)}")
    for line in failures:
        print(line)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        return verify(args.verify)
    files = collect()
    manifest = {"generated_at": datetime.now(UTC).isoformat(), "zones": ZONES,
                "file_count": len(files), "files": files}
    DEFAULT_OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DEFAULT_OUT} files={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
