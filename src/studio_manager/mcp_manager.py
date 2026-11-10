"""MCP registry and activation policy. Activation itself is intentionally not exposed."""

from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from studio_manager.service import DomainError, now_iso

LoopbackHost = Literal["127.0.0.1", "localhost"]
Permission = Literal["read_scene", "write_scene", "render", "execute_code"]

WRITE_PERMISSIONS = {"write_scene", "render", "execute_code"}


class MCPRegistration(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")]
    source_url: Annotated[str, Field(max_length=500, pattern=r"^https://")] | None = None
    version: Annotated[str, Field(min_length=1, max_length=60)]
    license: Annotated[str, Field(min_length=1, max_length=60)]
    bind_host: LoopbackHost
    permissions: list[Permission] = Field(default_factory=list)


class MCPManager:
    """Registry only. Nothing here starts, enables or contacts an MCP server."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def list_servers(self) -> list[dict[str, object]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT id,name,source_url,version,license,bind_host,permissions_json,status,enabled "
                    "FROM mcp_servers ORDER BY name"
                )
            ).mappings()
            return [dict(row) for row in rows]

    def _audit(self, connection: Connection, actor: str, action: str, server_id: str, after: dict[str, object]) -> None:
        connection.execute(
            text(
                "INSERT INTO audit_events(actor,action,subject_kind,subject_id,before_json,after_json,created_at) "
                "VALUES(:actor,:action,'MCP_SERVER',:id,NULL,:after,:created)"
            ),
            {
                "actor": actor,
                "action": action,
                "id": server_id,
                "after": json.dumps(after, sort_keys=True),
                "created": now_iso(),
            },
        )

    def register(self, payload: MCPRegistration, actor: str = "creative-director") -> dict[str, object]:
        server_id = f"mcp_{uuid4().hex}"
        record = {
            "id": server_id,
            "name": payload.name,
            "source_url": payload.source_url,
            "version": payload.version,
            "license": payload.license,
            "bind_host": payload.bind_host,
            "permissions_json": json.dumps(sorted(payload.permissions)),
            "status": "REGISTERED",
            "enabled": 0,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO mcp_servers("
                        "id,name,source_url,version,license,bind_host,permissions_json,status,enabled"
                        ") VALUES("
                        ":id,:name,:source_url,:version,:license,:bind_host,:permissions_json,:status,:enabled"
                        ")"
                    ),
                    record,
                )
                self._audit(connection, actor, "REGISTER", server_id, record)
        except IntegrityError as exc:
            raise DomainError("MCP server name already registered", 409) from exc
        return record

    def activation_check(self, server_id: str) -> dict[str, object]:
        """Report whether activation would be permitted. Never mutates state."""
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM mcp_servers WHERE id=:id"), {"id": server_id}
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DomainError("MCP server not found", 404)
            enabled_rows = connection.execute(
                text("SELECT id,name,permissions_json FROM mcp_servers WHERE enabled=1")
            ).mappings()
            enabled = [dict(item) for item in enabled_rows]

        reasons: list[str] = []
        permissions = set(json.loads(row["permissions_json"] or "[]"))
        if row["bind_host"] not in {"127.0.0.1", "localhost"}:
            reasons.append("bind host must be loopback")
        if "execute_code" in permissions:
            reasons.append("execute_code is denied by policy (allow_unreviewed_arbitrary_code=false)")
        if permissions & WRITE_PERMISSIONS and enabled:
            reasons.append("another MCP server is already enabled; only one write-capable server is allowed")
        return {
            "server_id": server_id,
            "name": row["name"],
            "would_enable": not reasons,
            "reasons": reasons,
            "active_servers": len(enabled),
            "note": "Activation is not implemented in this phase; this is a policy preview only.",
        }
