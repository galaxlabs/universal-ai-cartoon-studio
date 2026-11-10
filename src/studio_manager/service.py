from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from studio_manager.config import PROJECT_ROOT
from studio_manager.contracts import (
    ApprovalCreate,
    AssetCreate,
    AssetVersionCreate,
    AssetVersionTransition,
    CharacterCreate,
    EpisodeCreate,
    JobCreate,
    JobTransition,
    ProjectCreate,
    SceneCreate,
    SeriesCreate,
    ShotCreate,
)

JOB_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"QUEUED", "CANCELLED"},
    "QUEUED": {"RUNNING", "BLOCKED", "CANCELLED"},
    "RUNNING": {"VALIDATING", "FAILED", "BLOCKED", "CANCELLED"},
    "VALIDATING": {"PENDING_APPROVAL", "FAILED", "BLOCKED"},
    "PENDING_APPROVAL": {"APPROVED", "BLOCKED"},
    "APPROVED": {"PUBLISHED"},
    "FAILED": {"ROLLED_BACK"},
    "BLOCKED": {"ROLLED_BACK"},
    "CANCELLED": set(),
    "PUBLISHED": set(),
    "ROLLED_BACK": set(),
}


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class StudioService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.allowed_workspaces = (
            (PROJECT_ROOT / "storage" / "10_DEVELOPMENT").resolve(),
            (PROJECT_ROOT / "storage" / "20_TEMP").resolve(),
        )

    def _workspace(self, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            raise DomainError("workspace_path must be absolute")
        resolved = path.resolve(strict=False)
        if not any(resolved.is_relative_to(root) for root in self.allowed_workspaces):
            raise DomainError("workspace_path must be inside managed development or temporary storage")
        return str(resolved)

    @staticmethod
    def _row(connection: Connection, table: str, item_id: str) -> dict[str, object]:
        allowed = {
            "projects",
            "series",
            "episodes",
            "scenes",
            "shots",
            "characters",
            "assets",
            "asset_versions",
            "character_versions",
            "production_jobs",
            "approvals",
        }
        if table not in allowed:
            raise DomainError("invalid table", 500)
        row = (
            connection.execute(text(f"SELECT * FROM {table} WHERE id=:id"), {"id": item_id})  # noqa: S608
            .mappings()
            .first()
        )
        if row is None:
            raise DomainError(f"{table.rstrip('s')} not found", 404)
        return dict(row)

    @staticmethod
    def _audit(
        connection: Connection,
        actor: str,
        action: str,
        subject_kind: str,
        subject_id: str,
        before: dict[str, object] | None,
        after: dict[str, object] | None,
    ) -> None:
        connection.execute(
            text(
                "INSERT INTO audit_events(actor,action,subject_kind,subject_id,before_json,after_json,created_at) "
                "VALUES(:actor,:action,:kind,:id,:before,:after,:created)"
            ),
            {
                "actor": actor,
                "action": action,
                "kind": subject_kind,
                "id": subject_id,
                "before": json.dumps(before, sort_keys=True) if before else None,
                "after": json.dumps(after, sort_keys=True) if after else None,
                "created": now_iso(),
            },
        )

    def _write(self, operation):
        try:
            with self.engine.begin() as connection:
                return operation(connection)
        except IntegrityError as exc:
            raise DomainError("record conflicts with an existing value or missing parent", 409) from exc

    def create_project(self, payload: ProjectCreate, actor: str = "creative-director") -> dict[str, object]:
        item_id = new_id("prj")
        created = now_iso()
        root = PROJECT_ROOT / "storage" / "10_DEVELOPMENT" / "projects" / item_id

        def operation(connection: Connection):
            connection.execute(
                text("INSERT INTO projects VALUES(:id,:name,:status,:root,:created,:updated)"),
                {
                    "id": item_id,
                    "name": payload.name,
                    "status": payload.status,
                    "root": str(root),
                    "created": created,
                    "updated": created,
                },
            )
            row = self._row(connection, "projects", item_id)
            self._audit(connection, actor, "CREATE", "PROJECT", item_id, None, row)
            return row

        return self._write(operation)

    def _create_catalog_child(self, table: str, values: dict[str, object], actor: str) -> dict[str, object]:
        item_id = new_id(table[:3])
        columns = ["id", *values]
        placeholders = [f":{column}" for column in columns]
        parameters = {"id": item_id, **values}

        def operation(connection: Connection):
            statement = f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join(placeholders)})"
            connection.execute(text(statement), parameters)
            row = self._row(connection, table, item_id)
            self._audit(connection, actor, "CREATE", table.rstrip("s").upper(), item_id, None, row)
            return row

        return self._write(operation)

    def create_series(self, payload: SeriesCreate, actor: str = "creative-director") -> dict[str, object]:
        return self._create_catalog_child("series", payload.model_dump(), actor)

    def create_episode(self, payload: EpisodeCreate, actor: str = "creative-director") -> dict[str, object]:
        return self._create_catalog_child("episodes", payload.model_dump(), actor)

    def create_scene(self, payload: SceneCreate, actor: str = "creative-director") -> dict[str, object]:
        return self._create_catalog_child("scenes", payload.model_dump(), actor)

    def create_shot(self, payload: ShotCreate, actor: str = "creative-director") -> dict[str, object]:
        return self._create_catalog_child("shots", payload.model_dump(), actor)

    def create_character(self, payload: CharacterCreate, actor: str = "creative-director") -> dict[str, object]:
        return self._create_catalog_child("characters", payload.model_dump(), actor)

    def create_asset(self, payload: AssetCreate, actor: str = "creative-director") -> dict[str, object]:
        values = payload.model_dump()
        values["protected"] = int(payload.protected)
        return self._create_catalog_child("assets", values, actor)

    def create_asset_version(
        self,
        asset_id: str,
        payload: AssetVersionCreate,
        actor: str = "creative-director",
    ) -> dict[str, object]:
        item_id = new_id("av")
        workspace = self._workspace(payload.workspace_path)

        def operation(connection: Connection):
            self._row(connection, "assets", asset_id)
            version = connection.execute(
                text("SELECT COALESCE(MAX(version),0)+1 FROM asset_versions WHERE asset_id=:id"), {"id": asset_id}
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO asset_versions(id,asset_id,version,status,workspace_path,sha256,created_at) "
                    "VALUES(:id,:asset,:version,:status,:workspace,:sha,:created)"
                ),
                {
                    "id": item_id,
                    "asset": asset_id,
                    "version": version,
                    "status": payload.status,
                    "workspace": workspace,
                    "sha": payload.sha256,
                    "created": now_iso(),
                },
            )
            row = self._row(connection, "asset_versions", item_id)
            self._audit(connection, actor, "CREATE_VERSION", "ASSET", asset_id, None, row)
            return row

        return self._write(operation)

    def transition_asset_version(
        self,
        asset_version_id: str,
        payload: AssetVersionTransition,
        actor: str = "creative-director",
    ) -> dict[str, object]:
        allowed = {"DRAFT": {"VALIDATING"}, "VALIDATING": {"PENDING_APPROVAL"}}

        def operation(connection: Connection):
            before = self._row(connection, "asset_versions", asset_version_id)
            current = str(before["status"])
            if payload.target_status not in allowed.get(current, set()):
                raise DomainError(f"invalid asset version transition: {current} -> {payload.target_status}", 409)
            connection.execute(
                text("UPDATE asset_versions SET status=:status WHERE id=:id"),
                {"status": payload.target_status, "id": asset_version_id},
            )
            after = self._row(connection, "asset_versions", asset_version_id)
            self._audit(connection, actor, "TRANSITION", "ASSET_VERSION", asset_version_id, before, after)
            return after

        return self._write(operation)

    def create_job(self, payload: JobCreate) -> dict[str, object]:
        item_id = new_id("job")
        workspace = self._workspace(payload.workspace_path)

        def operation(connection: Connection):
            self._row(connection, "projects", payload.project_id)
            created = now_iso()
            connection.execute(
                text(
                    "INSERT INTO production_jobs("
                    "id,project_id,job_type,status,target_application,workspace_path,requested_by,created_at"
                    ") "
                    "VALUES(:id,:project,:type,'DRAFT',:target,:workspace,:actor,:created)"
                ),
                {
                    "id": item_id,
                    "project": payload.project_id,
                    "type": payload.job_type,
                    "target": payload.target_application,
                    "workspace": workspace,
                    "actor": payload.requested_by,
                    "created": created,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO job_events(job_id,sequence,event_type,payload_json,created_at) "
                    "VALUES(:id,1,'CREATED',:payload,:created)"
                ),
                {
                    "id": item_id,
                    "payload": json.dumps({"requested_by": payload.requested_by}),
                    "created": created,
                },
            )
            row = self._row(connection, "production_jobs", item_id)
            self._audit(connection, payload.requested_by, "CREATE", "JOB", item_id, None, row)
            return row

        return self._write(operation)

    def _transition_job(self, connection: Connection, job_id: str, payload: JobTransition) -> dict[str, object]:
        before = self._row(connection, "production_jobs", job_id)
        current = str(before["status"])
        if payload.target_status not in JOB_TRANSITIONS.get(current, set()):
            raise DomainError(f"invalid job transition: {current} -> {payload.target_status}", 409)
        sequence = connection.execute(
            text("SELECT COALESCE(MAX(sequence),0)+1 FROM job_events WHERE job_id=:id"), {"id": job_id}
        ).scalar_one()
        timestamps: dict[str, object] = {"started": None, "finished": None}
        if payload.target_status == "RUNNING":
            timestamps["started"] = now_iso()
        if payload.target_status in {"PUBLISHED", "FAILED", "CANCELLED", "ROLLED_BACK"}:
            timestamps["finished"] = now_iso()
        connection.execute(
            text(
                "UPDATE production_jobs SET status=:status, "
                "started_at=COALESCE(:started,started_at), finished_at=COALESCE(:finished,finished_at) WHERE id=:id"
            ),
            {
                "status": payload.target_status,
                "started": timestamps["started"],
                "finished": timestamps["finished"],
                "id": job_id,
            },
        )
        connection.execute(
            text(
                "INSERT INTO job_events(job_id,sequence,event_type,payload_json,created_at) "
                "VALUES(:id,:sequence,:event,:payload,:created)"
            ),
            {
                "id": job_id,
                "sequence": sequence,
                "event": f"STATUS_{payload.target_status}",
                "payload": json.dumps(payload.payload, sort_keys=True),
                "created": now_iso(),
            },
        )
        after = self._row(connection, "production_jobs", job_id)
        self._audit(connection, payload.actor, "TRANSITION", "JOB", job_id, before, after)
        return after

    def transition_job(self, job_id: str, payload: JobTransition) -> dict[str, object]:
        return self._write(lambda connection: self._transition_job(connection, job_id, payload))

    def create_approval(self, payload: ApprovalCreate) -> dict[str, object]:
        item_id = new_id("apr")
        table_by_subject = {
            "JOB": "production_jobs",
            "ASSET_VERSION": "asset_versions",
            "CHARACTER_VERSION": "character_versions",
        }

        def operation(connection: Connection):
            subject = (
                None
                if payload.subject_kind == "MCP_OPERATION"
                else self._row(connection, table_by_subject[payload.subject_kind], payload.subject_id)
            )
            if payload.subject_kind == "JOB":
                assert subject is not None
                if subject["status"] != "PENDING_APPROVAL":
                    raise DomainError("job approvals require PENDING_APPROVAL status", 409)
                target = "APPROVED" if payload.decision == "APPROVED" else "BLOCKED"
                self._transition_job(
                    connection,
                    payload.subject_id,
                    JobTransition(
                        target_status=target,
                        actor=payload.decided_by,
                        payload={"decision": payload.decision},
                    ),
                )
            if payload.subject_kind == "ASSET_VERSION":
                assert subject is not None
                if subject["status"] != "PENDING_APPROVAL":
                    raise DomainError("asset version approvals require PENDING_APPROVAL status", 409)
                if payload.decision == "APPROVED":
                    if not subject["sha256"]:
                        raise DomainError("asset version approval requires a SHA-256 digest", 409)
                    workspace = Path(str(subject["workspace_path"] or ""))
                    if not workspace.exists():
                        raise DomainError("asset version approval requires an existing workspace path", 409)
                    connection.execute(
                        text("UPDATE asset_versions SET status='APPROVED' WHERE id=:id"),
                        {"id": payload.subject_id},
                    )
            connection.execute(
                text(
                    "INSERT INTO approvals("
                    "id,subject_kind,subject_id,decision,decided_by,notes,evidence_json,created_at"
                    ") "
                    "VALUES(:id,:kind,:subject,:decision,:actor,:notes,:evidence,:created)"
                ),
                {
                    "id": item_id,
                    "kind": payload.subject_kind,
                    "subject": payload.subject_id,
                    "decision": payload.decision,
                    "actor": payload.decided_by,
                    "notes": payload.notes,
                    "evidence": json.dumps(payload.evidence, sort_keys=True),
                    "created": now_iso(),
                },
            )
            row = self._row(connection, "approvals", item_id)
            self._audit(connection, payload.decided_by, "DECIDE", payload.subject_kind, payload.subject_id, None, row)
            return row

        return self._write(operation)

    def snapshot(self) -> dict[str, object]:
        with self.engine.connect() as connection:
            result: dict[str, object] = {}
            tables = (
                "projects",
                "series",
                "episodes",
                "scenes",
                "shots",
                "characters",
                "assets",
                "asset_versions",
                "production_jobs",
                "approvals",
            )
            for table in tables:
                query = text(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 50")  # noqa: S608
                result[table] = [dict(row) for row in connection.execute(query).mappings()]
            events = connection.execute(
                text("SELECT * FROM job_events ORDER BY id DESC LIMIT 100")
            ).mappings()
            result["job_events"] = [dict(row) for row in events]
            return result
