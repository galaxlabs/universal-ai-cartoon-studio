"""Inert versioned metadata, never a model/tool runner or execution permission grant."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Literal

from sqlalchemy import Connection, Engine, Table, func, insert, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from studio_manager.agent_contracts import AgentCreate, AgentVersionCreate, SkillCreate, SkillVersionCreate
from studio_manager.agent_models import StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion
from studio_manager.service import DomainError, StudioService, new_id, now_iso

Kind = Literal["agent", "skill"]
TABLES = {
    "agent": (StudioAgent.__table__, StudioAgentVersion.__table__, "agent_id"),
    "skill": (StudioSkill.__table__, StudioSkillVersion.__table__, "skill_id"),
}


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class AgentRegistry:
    def __init__(self, engine: Engine):
        self.engine = engine

    def _write(self, operation: Callable[[Connection], dict]) -> dict:
        try:
            with self.engine.connect() as connection:
                # Acquire the SQLite writer lock before MAX(version)+1 or existence
                # reads. Keep this short: no filesystem/network/tool work inside.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    result = operation(connection)
                    connection.commit()
                    return result
                except Exception:
                    connection.rollback()
                    raise
        except IntegrityError as exc:
            raise DomainError("registry record conflicts with an existing record or missing parent", 409) from exc
        except OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise DomainError("registry writer is busy; retry later", 503) from exc
            raise

    @staticmethod
    def _owner(connection: Connection, table: Table, owner_id: str) -> None:
        if connection.execute(select(table.c.id).where(table.c.id == owner_id)).first() is None:
            raise DomainError("registry definition not found", 404)

    @staticmethod
    def _serialize(row: dict) -> dict:
        result = dict(row)
        if "enabled" in result:
            result["enabled"] = bool(result["enabled"])
        for key in tuple(result):
            if key.endswith("_json"):
                result[key.removesuffix("_json")] = json.loads(str(result.pop(key)))
        result["registry_namespace"] = "studio"
        return result

    @staticmethod
    def _page(limit: int, offset: int) -> None:
        if not 1 <= limit <= 100 or offset < 0:
            raise DomainError("invalid pagination")

    def list_definitions(self, kind: Kind, limit: int = 50, offset: int = 0) -> dict:
        self._page(limit, offset)
        table = TABLES[kind][0]
        with self.engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(table)).scalar_one()
            rows = connection.execute(select(table).order_by(table.c.code).limit(limit).offset(offset)).mappings()
            return {"items": [self._serialize(dict(r)) for r in rows], "count": count, "limit": limit, "offset": offset}

    def list_agents(self, limit: int = 50, offset: int = 0) -> dict:
        return self.list_definitions("agent", limit, offset)

    def list_skills(self, limit: int = 50, offset: int = 0) -> dict:
        return self.list_definitions("skill", limit, offset)

    def list_versions(self, kind: Kind, owner_id: str, limit: int = 50, offset: int = 0) -> dict:
        self._page(limit, offset)
        parent, table, fk = TABLES[kind]
        with self.engine.connect() as connection:
            self._owner(connection, parent, owner_id)
            where = table.c[fk] == owner_id
            count = connection.execute(select(func.count()).select_from(table).where(where)).scalar_one()
            rows = connection.execute(
                select(table).where(where).order_by(table.c.version).limit(limit).offset(offset)
            ).mappings()
            return {"items": [self._serialize(dict(r)) for r in rows], "count": count, "limit": limit, "offset": offset}

    def create_agent(self, code: str, name: str, role: str, description: str = "", actor: str = "local-api-user"):
        payload = AgentCreate(code=code, name=name, role=role, description=description)
        return self._create_definition("agent", payload.model_dump(), actor)

    def create_skill(self, code: str, name: str, description: str = "", actor: str = "local-api-user"):
        payload = SkillCreate(code=code, name=name, description=description)
        return self._create_definition("skill", payload.model_dump(), actor)

    def _create_definition(self, kind: Kind, fields: dict, actor: str) -> dict:
        table = TABLES[kind][0]
        now = now_iso()
        values = {"id": new_id(kind), **fields, "enabled": 0, "created_at": now}
        if kind == "agent":
            values["updated_at"] = now

        def operation(connection: Connection) -> dict:
            connection.execute(insert(table).values(**values))
            result = self._serialize(values)
            StudioService._audit(connection, actor, "CREATE", f"STUDIO_{kind.upper()}", values["id"], None, result)
            return result

        return self._write(operation)

    def create_agent_version(
        self, agent_id: str, instruction: str, model_profile: str = "",
        allowed_tools: list[str] | None = None, allowed_skills: list[str] | None = None,
        config: dict | None = None, actor: str = "local-api-user",
    ) -> dict:
        payload = AgentVersionCreate(
            instruction=instruction, model_profile=model_profile, allowed_tools=allowed_tools or [],
            allowed_skills=allowed_skills or [], config=config or {},
        )
        data = payload.model_dump()
        fields = {"instruction": data["instruction"], "model_profile": data["model_profile"]}
        for key in ("allowed_tools", "allowed_skills", "config"):
            fields[key + "_json"] = json.dumps(data[key], sort_keys=True)
        return self._create_version("agent", agent_id, fields, actor, payload.allowed_skills)

    def create_skill_version(
        self, skill_id: str, instructions: str, input_schema: dict | None = None,
        output_schema: dict | None = None, actor: str = "local-api-user",
    ) -> dict:
        payload = SkillVersionCreate(
            instructions=instructions, input_schema=input_schema or {}, output_schema=output_schema or {},
        )
        fields = {
            "instructions": payload.instructions,
            "input_schema_json": json.dumps(payload.input_schema, sort_keys=True),
            "output_schema_json": json.dumps(payload.output_schema, sort_keys=True),
        }
        return self._create_version("skill", skill_id, fields, actor, [])

    def _create_version(self, kind: Kind, owner_id: str, fields: dict, actor: str, skill_versions: list[str]) -> dict:
        parent, table, fk = TABLES[kind]

        def operation(connection: Connection) -> dict:
            self._owner(connection, parent, owner_id)
            skills = StudioSkillVersion.__table__
            for reference in skill_versions:
                if connection.execute(select(skills.c.id).where(skills.c.id == reference)).first() is None:
                    raise DomainError(
                        "studio skill version not found; references must pin exact studio version IDs", 404,
                    )
            number = connection.execute(
                select(func.coalesce(func.max(table.c.version), 0) + 1).where(table.c[fk] == owner_id)
            ).scalar_one()
            values = {
                "id": new_id(kind + "v"), fk: owner_id, "version": number,
                "created_at": now_iso(), "status": "DRAFT", **fields,
            }
            connection.execute(insert(table).values(**values))
            audit = {
                "id": values["id"], "owner_id": owner_id, "version": number,
                "status": "DRAFT", "content_sha256": fingerprint(fields),
                "skill_version_ids": skill_versions,
            }
            StudioService._audit(connection, actor, "CREATE_VERSION", f"STUDIO_{kind.upper()}_VERSION",
                                 values["id"], None, audit)
            return self._serialize(values)

        return self._write(operation)

    def list_legacy_skills(self, limit: int = 50, offset: int = 0) -> dict:
        self._page(limit, offset)
        with self.engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM skills")).scalar_one()
            rows = connection.execute(
                text("SELECT id,name,source,version,status,enabled FROM skills "
                     "ORDER BY id LIMIT :limit OFFSET :offset"),
                {"limit": limit, "offset": offset},
            ).mappings()
            return {
                "items": [{**dict(r), "enabled": bool(r["enabled"]), "registry_namespace": "legacy-import"}
                          for r in rows],
                "count": count, "limit": limit, "offset": offset, "read_only": True,
            }
