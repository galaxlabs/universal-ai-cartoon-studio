from __future__ import annotations

import json
from collections.abc import Mapping

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from studio_manager.service import DomainError, StudioService, new_id, now_iso

TABLE_FIELDS: dict[str, frozenset[str]] = {
    "projects": frozenset({"status", "name"}),
    "assets": frozenset({"project_id", "asset_type", "lifecycle_state", "protected", "code", "name"}),
    "asset_versions": frozenset({"asset_id", "status"}),
    "characters": frozenset({"project_id", "bible_status", "code", "name"}),
    "character_variants": frozenset({"character_id", "status", "code", "name"}),
    "production_jobs": frozenset({"project_id", "status", "job_type", "target_application"}),
    "approvals": frozenset({"subject_kind", "subject_id", "decision", "decided_by"}),
    "audit_events": frozenset({"subject_kind", "subject_id", "action", "actor"}),
    "import_batches": frozenset({"source_kind", "status", "dry_run"}),
    "backups": frozenset({"subject_kind", "subject_id", "restore_tested"}),
}

UPDATE_FIELDS: dict[str, frozenset[str]] = {
    "projects": frozenset({"name", "status"}),
    "assets": frozenset({"name", "lifecycle_state", "protected"}),
    "characters": frozenset({"name", "bible_status"}),
    "character_variants": frozenset({"name", "description", "config_json", "status"}),
}

DELETABLE = frozenset({"projects", "assets", "characters", "character_variants"})


class Phase03AService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.legacy = StudioService(engine)

    @staticmethod
    def _validate_table(table: str) -> None:
        if table not in TABLE_FIELDS:
            raise DomainError("unsupported record type", 500)

    def list_records(
        self,
        table: str,
        *,
        limit: int,
        offset: int,
        filters: Mapping[str, object | None],
    ) -> dict[str, object]:
        self._validate_table(table)
        clauses: list[str] = []
        parameters: dict[str, object] = {"limit": limit, "offset": offset}
        for key, value in filters.items():
            if value is None:
                continue
            if key not in TABLE_FIELDS[table]:
                raise DomainError(f"unsupported filter: {key}")
            clauses.append(f"{key}=:{key}")
            parameters[key] = int(value) if isinstance(value, bool) else value
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.engine.connect() as connection:
            count = connection.execute(text(f"SELECT COUNT(*) FROM {table}{where}"), parameters).scalar_one()  # noqa: S608
            rows = connection.execute(
                text(f"SELECT * FROM {table}{where} ORDER BY rowid DESC LIMIT :limit OFFSET :offset"),  # noqa: S608
                parameters,
            ).mappings()
            return {"items": [dict(row) for row in rows], "count": count, "limit": limit, "offset": offset}

    def get_record(self, table: str, item_id: str) -> dict[str, object]:
        self._validate_table(table)
        key = "id" if table != "app_settings" else "key"
        with self.engine.connect() as connection:
            row = connection.execute(
                text(f"SELECT * FROM {table} WHERE {key}=:id"),  # noqa: S608
                {"id": item_id},
            ).mappings().first()
        if row is None:
            raise DomainError("record not found", 404)
        return dict(row)

    @staticmethod
    def _audit(
        connection: Connection,
        actor: str,
        action: str,
        table: str,
        item_id: str,
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
                "kind": table.rstrip("s").upper(),
                "id": item_id,
                "before": json.dumps(before, sort_keys=True) if before else None,
                "after": json.dumps(after, sort_keys=True) if after else None,
                "created": now_iso(),
            },
        )

    def update_record(
        self,
        table: str,
        item_id: str,
        changes: Mapping[str, object],
        actor: str,
    ) -> dict[str, object]:
        if table not in UPDATE_FIELDS:
            raise DomainError("record type is append-only or lifecycle-managed", 405)
        values = {key: value for key, value in changes.items() if value is not None}
        if not values:
            raise DomainError("at least one update field is required")
        if not values.keys() <= UPDATE_FIELDS[table]:
            raise DomainError("unsupported update field")
        if "protected" in values:
            values["protected"] = int(bool(values["protected"]))
        assignments = ",".join(f"{key}=:{key}" for key in values)
        if table in {"projects", "character_variants"}:
            assignments += ",updated_at=:updated_at"
            values["updated_at"] = now_iso()
        try:
            with self.engine.begin() as connection:
                before = self._connection_row(connection, table, item_id)
                connection.execute(
                    text(f"UPDATE {table} SET {assignments} WHERE id=:id"),  # noqa: S608
                    {**values, "id": item_id},
                )
                after = self._connection_row(connection, table, item_id)
                self._audit(connection, actor, "UPDATE", table, item_id, before, after)
                return after
        except IntegrityError as exc:
            raise DomainError("update conflicts with an existing record", 409) from exc

    @staticmethod
    def _connection_row(connection: Connection, table: str, item_id: str) -> dict[str, object]:
        row = connection.execute(text(f"SELECT * FROM {table} WHERE id=:id"), {"id": item_id}).mappings().first()  # noqa: S608
        if row is None:
            raise DomainError("record not found", 404)
        return dict(row)

    def delete_record(self, table: str, item_id: str, actor: str) -> dict[str, object]:
        if table not in DELETABLE:
            raise DomainError("record type cannot be deleted", 405)
        try:
            with self.engine.begin() as connection:
                before = self._connection_row(connection, table, item_id)
                if table == "assets" and before.get("protected"):
                    raise DomainError("protected assets cannot be deleted", 409)
                connection.execute(text(f"DELETE FROM {table} WHERE id=:id"), {"id": item_id})  # noqa: S608
                self._audit(connection, actor, "DELETE", table, item_id, before, None)
                return {"deleted": True, "id": item_id}
        except (IntegrityError, DBAPIError) as exc:
            raise DomainError("record has dependent or protected records and cannot be deleted", 409) from exc

    def create_character_variant(
        self,
        character_id: str,
        payload: Mapping[str, object],
        actor: str,
    ) -> dict[str, object]:
        item_id = new_id("cv")
        created = now_iso()
        try:
            with self.engine.begin() as connection:
                self._connection_row(connection, "characters", character_id)
                connection.execute(
                    text(
                        "INSERT INTO character_variants("
                        "id,character_id,code,name,description,config_json,status,created_at,updated_at"
                        ") VALUES(:id,:character,:code,:name,:description,:config,:status,:created,:created)"
                    ),
                    {
                        "id": item_id,
                        "character": character_id,
                        "code": payload["code"],
                        "name": payload["name"],
                        "description": payload.get("description"),
                        "config": json.dumps(payload.get("config", {}), sort_keys=True),
                        "status": payload["status"],
                        "created": created,
                    },
                )
                row = self._connection_row(connection, "character_variants", item_id)
                self._audit(connection, actor, "CREATE", "character_variants", item_id, None, row)
                return row
        except IntegrityError as exc:
            raise DomainError("character variant conflicts with an existing record", 409) from exc
