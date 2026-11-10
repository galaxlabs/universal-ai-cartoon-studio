from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, text

from studio_manager.service import DomainError, new_id, now_iso


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BackupService:
    def __init__(self, engine: Engine, database_path: Path, backup_root: Path, recovery_root: Path):
        self.engine = engine
        self.database_path = database_path
        self.backup_root = backup_root.resolve(strict=False)
        self.recovery_root = recovery_root.resolve(strict=False)

    def create(self, actor: str = "local-api-user") -> dict[str, object]:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        destination = self.backup_root / f"studio-{stamp}.db"
        temporary = destination.with_suffix(".db.tmp")
        source = sqlite3.connect(self.database_path)
        target = sqlite3.connect(temporary)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        try:
            verification = self.verify(temporary)
            if verification["integrity_check"] != "ok":
                raise DomainError("database backup failed integrity verification", 500)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        record_id = new_id("bak")
        digest = file_sha256(destination)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO backups(id,subject_kind,subject_id,path,sha256,restore_tested,created_at) "
                    "VALUES(:id,'DATABASE','studio.db',:path,:sha,1,:created)"
                ),
                {"id": record_id, "path": str(destination), "sha": digest, "created": now_iso()},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events(actor,action,subject_kind,subject_id,after_json,created_at) "
                    "VALUES(:actor,'BACKUP','DATABASE',:id,:after,:created)"
                ),
                {
                    "actor": actor,
                    "id": record_id,
                    "after": json.dumps({"path": str(destination), "sha256": digest}, sort_keys=True),
                    "created": now_iso(),
                },
            )
        return {
            "id": record_id,
            "path": str(destination),
            "sha256": digest,
            "bytes": destination.stat().st_size,
            **verification,
        }

    @staticmethod
    def verify(path: Path) -> dict[str, object]:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        finally:
            connection.close()
        return {"integrity_check": integrity, "migration_revision": revision, "restore_open_test": integrity == "ok"}

    def restore_copy(self, backup: Path, destination: Path) -> dict[str, object]:
        source = backup.resolve(strict=True)
        if not source.is_relative_to(self.backup_root) or source.is_symlink():
            raise DomainError("backup must be a regular file inside managed backup storage")
        destination = destination.resolve(strict=False)
        if destination == self.database_path.resolve(strict=False):
            raise DomainError("live database restore requires an offline recovery procedure", 409)
        self.recovery_root.mkdir(parents=True, exist_ok=True)
        if not destination.is_relative_to(self.recovery_root) or destination.exists():
            raise DomainError("restore destination must be a new file inside managed recovery storage")
        with self.engine.connect() as connection:
            record = connection.execute(
                text("SELECT sha256 FROM backups WHERE path=:path ORDER BY created_at DESC LIMIT 1"),
                {"path": str(source)},
            ).first()
        if record is None or file_sha256(source) != record[0]:
            raise DomainError("backup is unregistered or its SHA-256 does not match", 409)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        target_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(target_connection)
        finally:
            target_connection.close()
            source_connection.close()
        try:
            verification = self.verify(temporary)
            if verification["integrity_check"] != "ok":
                raise DomainError("restored copy failed integrity verification", 500)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {"destination": str(destination), "sha256": file_sha256(destination), **verification}
