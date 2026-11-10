from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from studio_manager.config import PROJECT_ROOT
from studio_manager.service import DomainError, new_id, now_iso
from studio_manager.storage_service import LocalStorageService


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def bytes_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:32]}"


@dataclass(frozen=True, slots=True)
class ImportItem:
    source_key: str
    source_hash: str
    target_kind: str
    target_table: str
    target_id: str
    values: dict[str, object]
    unknown_fields: dict[str, object]


class SourceAdapter(Protocol):
    source_kind: str

    def parse(self, path: Path, payload: object, raw_bytes: bytes) -> list[ImportItem]: ...


class SkillsManifestAdapter:
    source_kind = "PHASE02_SKILLS"
    known = frozenset({"id", "name", "source", "version", "status"})

    def parse(self, path: Path, payload: object, raw_bytes: bytes) -> list[ImportItem]:
        if path != (PROJECT_ROOT / "config" / "phase02.skills.json").resolve():
            raise DomainError("skills import source is not allow-listed")
        if not isinstance(payload, dict) or not isinstance(payload.get("skills"), list):
            raise DomainError("invalid Phase 02 skills manifest")
        items: list[ImportItem] = []
        for raw in payload["skills"]:
            if not isinstance(raw, dict) or not all(key in raw for key in ("id", "name", "status")):
                raise DomainError("invalid skill record in Phase 02 manifest")
            source_key = str(raw["id"])
            unknown = {key: value for key, value in raw.items() if key not in self.known}
            values: dict[str, object] = {
                "name": str(raw["name"]),
                "source": str(raw.get("source") or ""),
                "version": str(raw.get("version") or ""),
                "permissions_json": json.dumps({"imported_disabled": True}, sort_keys=True),
                "status": str(raw["status"]),
                "enabled": 0,
            }
            items.append(
                ImportItem(
                    source_key=source_key,
                    source_hash=canonical_hash(raw),
                    target_kind="SKILL",
                    target_table="skills",
                    target_id=source_key,
                    values=values,
                    unknown_fields=unknown,
                )
            )
        return items


class Phase02ReportAdapter:
    source_kind = "PHASE02_REPORT"
    known = frozenset({"generated_at", "phase", "status"})

    def parse(self, path: Path, payload: object, raw_bytes: bytes) -> list[ImportItem]:
        reports = (PROJECT_ROOT / "storage" / "80_REPORTS").resolve()
        if path.parent != reports or not path.name.startswith("phase02_") or path.suffix.lower() != ".json":
            raise DomainError("Phase 02 report source is not allow-listed")
        if not isinstance(payload, dict):
            raise DomainError("invalid Phase 02 report")
        source_key = path.name
        unknown = {key: value for key, value in payload.items() if key not in self.known}
        values: dict[str, object] = {
            "job_id": None,
            "asset_version_id": None,
            "validator": str(payload.get("phase") or "PHASE_02_REPORT"),
            "status": str(payload.get("status") or "RECORDED"),
            "report_path": str(path),
            "report_sha256": bytes_hash(raw_bytes),
            "created_at": str(payload.get("generated_at") or now_iso()),
        }
        return [
            ImportItem(
                source_key=source_key,
                source_hash=canonical_hash(payload),
                target_kind="VALIDATION_REPORT",
                target_table="validation_reports",
                target_id=stable_id("vr", f"{self.source_kind}:{source_key}"),
                values=values,
                unknown_fields=unknown,
            )
        ]


class ImportConflict(Exception):
    pass


class Phase02ImportService:
    adapters: dict[str, SourceAdapter] = {
        SkillsManifestAdapter.source_kind: SkillsManifestAdapter(),
        Phase02ReportAdapter.source_kind: Phase02ReportAdapter(),
    }

    def __init__(self, engine: Engine, evidence_storage: LocalStorageService):
        self.engine = engine
        self.evidence_storage = evidence_storage

    @staticmethod
    def _source_path(value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.is_symlink():
            raise DomainError("import source must not be a symlink")
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise DomainError("import source is not a file")
        return resolved

    @staticmethod
    def _row(connection: Connection, table: str, item_id: str) -> dict[str, object] | None:
        row = connection.execute(
            text(f"SELECT * FROM {table} WHERE id=:id"),  # noqa: S608
            {"id": item_id},
        ).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _insert_target(connection: Connection, item: ImportItem) -> dict[str, object]:
        values = {"id": item.target_id, **item.values}
        columns = ",".join(values)
        placeholders = ",".join(f":{key}" for key in values)
        connection.execute(
            text(f"INSERT INTO {item.target_table}({columns}) VALUES({placeholders})"),  # noqa: S608
            values,
        )
        return Phase02ImportService._row(connection, item.target_table, item.target_id) or {}

    @staticmethod
    def _update_target(connection: Connection, item: ImportItem) -> dict[str, object]:
        assignments = ",".join(f"{key}=:{key}" for key in item.values)
        connection.execute(
            text(f"UPDATE {item.target_table} SET {assignments} WHERE id=:id"),  # noqa: S608
            {**item.values, "id": item.target_id},
        )
        return Phase02ImportService._row(connection, item.target_table, item.target_id) or {}

    def run(self, source_kind: str, source_path: str, *, dry_run: bool, actor: str) -> dict[str, object]:
        adapter = self.adapters.get(source_kind)
        if adapter is None:
            raise DomainError("unsupported import source kind")
        path = self._source_path(source_path)
        raw_bytes = path.read_bytes()
        try:
            payload: Any = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            raise DomainError("import source is not valid JSON") from exc
        items = adapter.parse(path, payload, raw_bytes)
        batch_id = new_id("imp")
        started = now_iso()
        source_hash = bytes_hash(raw_bytes)
        unknown = {
            "batch_id": batch_id,
            "source_kind": source_kind,
            "source_path": str(path),
            "records": [{"source_key": item.source_key, "unknown_fields": item.unknown_fields} for item in items],
        }
        evidence = self.evidence_storage.write_bytes(
            f"imports/{batch_id}-unknown-fields.json",
            (json.dumps(unknown, indent=2, sort_keys=True) + "\n").encode(),
        )
        counts = {"created": 0, "updated": 0, "skipped": 0, "conflicts": 0, "records": len(items)}
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO import_batches("
                        "id,source_kind,source_path,source_hash,status,dry_run,counts_json,unknown_fields_path,started_at"
                        ") VALUES(:id,:kind,:path,:hash,'RUNNING',:dry,'{}',:unknown,:started)"
                    ),
                    {
                        "id": batch_id,
                        "kind": source_kind,
                        "path": str(path),
                        "hash": source_hash,
                        "dry": int(dry_run),
                        "unknown": evidence.absolute_path,
                        "started": started,
                    },
                )
                for item in items:
                    provenance = connection.execute(
                        text("SELECT * FROM import_records WHERE source_kind=:kind AND source_key=:key"),
                        {"kind": source_kind, "key": item.source_key},
                    ).mappings().first()
                    current = self._row(connection, item.target_table, item.target_id)
                    if provenance is None:
                        if current is not None:
                            counts["conflicts"] += 1
                            raise ImportConflict(f"manual record already exists for {item.source_key}")
                        counts["created"] += 1
                        if dry_run:
                            continue
                        after = self._insert_target(connection, item)
                        connection.execute(
                            text(
                                "INSERT INTO import_records("
                                "id,batch_id,source_kind,source_key,source_hash,target_kind,target_id,"
                                "target_fingerprint,imported_at) "
                                "VALUES(:id,:batch,:kind,:key,:hash,:target_kind,:target_id,:fingerprint,:imported)"
                            ),
                            {
                                "id": new_id("imr"),
                                "batch": batch_id,
                                "kind": source_kind,
                                "key": item.source_key,
                                "hash": item.source_hash,
                                "target_kind": item.target_kind,
                                "target_id": item.target_id,
                                "fingerprint": canonical_hash(after),
                                "imported": now_iso(),
                            },
                        )
                        continue
                    if current is None or canonical_hash(current) != provenance["target_fingerprint"]:
                        counts["conflicts"] += 1
                        raise ImportConflict(f"imported record was manually changed: {item.source_key}")
                    if provenance["source_hash"] == item.source_hash:
                        counts["skipped"] += 1
                        continue
                    counts["updated"] += 1
                    if dry_run:
                        continue
                    after = self._update_target(connection, item)
                    connection.execute(
                        text(
                            "UPDATE import_records SET batch_id=:batch,source_hash=:hash,"
                            "target_fingerprint=:fingerprint,"
                            "imported_at=:imported WHERE id=:id"
                        ),
                        {
                            "batch": batch_id,
                            "hash": item.source_hash,
                            "fingerprint": canonical_hash(after),
                            "imported": now_iso(),
                            "id": provenance["id"],
                        },
                    )
                status = "DRY_RUN" if dry_run else "COMPLETED"
                connection.execute(
                    text(
                        "UPDATE import_batches SET status=:status,counts_json=:counts,"
                        "completed_at=:completed WHERE id=:id"
                    ),
                    {
                        "status": status,
                        "counts": json.dumps(counts, sort_keys=True),
                        "completed": now_iso(),
                        "id": batch_id,
                    },
                )
                connection.execute(
                    text(
                        "INSERT INTO audit_events(actor,action,subject_kind,subject_id,after_json,created_at) "
                        "VALUES(:actor,'IMPORT','IMPORT_BATCH',:id,:after,:created)"
                    ),
                    {
                        "actor": actor,
                        "id": batch_id,
                        "after": json.dumps({"status": status, "counts": counts}, sort_keys=True),
                        "created": now_iso(),
                    },
                )
        except (ImportConflict, IntegrityError) as exc:
            counts["created"] = 0
            counts["updated"] = 0
            counts["conflicts"] = max(1, counts["conflicts"])
            message = str(exc) if isinstance(exc, ImportConflict) else "concurrent import conflict"
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO import_batches("
                        "id,source_kind,source_path,source_hash,status,dry_run,counts_json,unknown_fields_path,"
                        "error_json,started_at,completed_at) "
                        "VALUES(:id,:kind,:path,:hash,'CONFLICT',:dry,:counts,:unknown,:error,:started,:completed)"
                    ),
                    {
                        "id": batch_id,
                        "kind": source_kind,
                        "path": str(path),
                        "hash": source_hash,
                        "dry": int(dry_run),
                        "counts": json.dumps(counts, sort_keys=True),
                        "unknown": evidence.absolute_path,
                        "error": json.dumps({"message": message}),
                        "started": started,
                        "completed": now_iso(),
                    },
                )
            raise DomainError(message, 409) from exc
        except Exception:
            self.evidence_storage.delete(evidence.relative_path)
            raise
        return {
            "id": batch_id,
            "source_kind": source_kind,
            "source_hash": source_hash,
            "status": "DRY_RUN" if dry_run else "COMPLETED",
            "dry_run": dry_run,
            "counts": counts,
            "unknown_fields_path": evidence.absolute_path,
        }
