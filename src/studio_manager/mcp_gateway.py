"""Argument-aware, default-deny policy gateway for reviewed MCP integrations."""

from __future__ import annotations

import ast
import hashlib
import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Engine, text

from studio_manager.config import PROJECT_ROOT
from studio_manager.service import DomainError, now_iso

OperationSelector = Literal["tool", "method", "action"]
Application = Literal["BLENDER", "UNREAL"]
InvocationStatus = Literal["SUCCEEDED", "FAILED"]

_SENSITIVE_KEYS = {"authorization", "code", "password", "secret", "token"}
_SAFE_IMPORTS = {"bmesh", "bpy", "json", "math", "mathutils"}
_DENIED_CALLS = {"breakpoint", "compile", "eval", "exec", "input", "open", "__import__"}
_DENIED_ROOTS = {
    "asyncio", "ctypes", "http", "importlib", "os", "pathlib",
    "shutil", "socket", "subprocess", "sys", "urllib",
}


def approval_subject(server_id: str, operation: str) -> str:
    """Return the stable, Identifier-compatible approval subject for an operation."""
    digest = hashlib.sha256(f"{server_id}:{operation}".encode()).hexdigest()[:32]
    return f"mcpop_{digest}"


class MCPGatewayPolicy(BaseModel):
    application: Application
    operation_selector: OperationSelector
    allowed_operations: list[Annotated[str, Field(min_length=1, max_length=160)]]
    denied_operations: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list)
    write_operations: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list)
    approval_operations: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list)
    write_scopes: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_concurrency: int = Field(default=1, ge=1, le=4)
    retry_limit: int = Field(default=0, ge=0, le=2)
    rollback_strategy: Annotated[str, Field(min_length=1, max_length=120)] = "delete_isolated_output"
    enabled: bool = False

    @field_validator("write_scopes")
    @classmethod
    def validate_write_scopes(cls, values: list[str]) -> list[str]:
        allowed_roots = (
            (PROJECT_ROOT / "storage" / "10_DEVELOPMENT").resolve(),
            (PROJECT_ROOT / "storage" / "20_TEMP").resolve(),
        )
        normalized: list[str] = []
        for value in values:
            path = Path(value)
            if not path.is_absolute():
                raise ValueError("write scopes must be absolute")
            resolved = path.resolve(strict=False)
            if not any(resolved.is_relative_to(root) for root in allowed_roots):
                raise ValueError("write scopes must be inside managed development or temporary storage")
            normalized.append(str(resolved))
        return normalized


class MCPInvocationRequest(BaseModel):
    tool_name: Annotated[str, Field(min_length=1, max_length=160)]
    arguments: dict[str, Any] = Field(default_factory=dict)
    workspace_path: Annotated[str, Field(max_length=500)] | None = None
    approval_id: Annotated[str, Field(max_length=80)] | None = None
    actor: Annotated[str, Field(min_length=1, max_length=120)] = "studio-gateway"


class MCPInvocationCompletion(BaseModel):
    status: InvocationStatus
    attempt_count: int = Field(ge=1, le=3)
    duration_ms: int = Field(ge=0)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    rollback_status: Annotated[str, Field(max_length=80)] | None = None
    error_code: Annotated[str, Field(max_length=80)] | None = None


class MCPGateway:
    """Persists policy decisions and wraps trusted adapters with bounded execution."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._locks: dict[str, threading.BoundedSemaphore] = {}
        self._locks_guard = threading.Lock()

    @staticmethod
    def _matches(operation: str, patterns: list[str]) -> bool:
        return any(fnmatchcase(operation, pattern) for pattern in patterns)

    @staticmethod
    def _sanitize_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
        def clean(key: str, value: Any) -> Any:
            if key.lower() in _SENSITIVE_KEYS:
                raw = json.dumps(value, sort_keys=True, default=str)
                return {"redacted": True, "sha256": hashlib.sha256(raw.encode()).hexdigest(), "characters": len(raw)}
            if isinstance(value, dict):
                return {str(k): clean(str(k), v) for k, v in value.items()}
            if isinstance(value, list):
                return [clean(key, item) for item in value]
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            return str(value)

        return {str(key): clean(str(key), value) for key, value in arguments.items()}

    @staticmethod
    def _operation(selector: str, request: MCPInvocationRequest) -> str:
        if selector == "tool":
            return request.tool_name
        if selector == "method":
            if request.tool_name != "call" or not isinstance(request.arguments.get("method"), str):
                raise DomainError("method-selected servers require call with a string method", 403)
            return request.arguments["method"]
        if not isinstance(request.arguments.get("action"), str):
            raise DomainError("action-selected servers require a string action", 403)
        return request.arguments["action"]

    @staticmethod
    def _validate_code(code: str, scopes: list[Path]) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise DomainError("code failed safe syntax validation", 403) from exc
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [item.name.split(".")[0] for item in node.names]
                    if isinstance(node, ast.Import)
                    else [(node.module or "").split(".")[0]]
                )
                if any(name not in _SAFE_IMPORTS for name in names):
                    raise DomainError("code imports a denied module", 403)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in _DENIED_CALLS:
                    raise DomainError("code calls a denied builtin", 403)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in _DENIED_ROOTS
                ):
                    raise DomainError("code calls a denied module", 403)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                candidate = Path(node.value)
                if candidate.is_absolute():
                    resolved = candidate.resolve(strict=False)
                    if not any(resolved.is_relative_to(scope) for scope in scopes):
                        raise DomainError("code contains an out-of-scope absolute path", 403)

    def set_policy(self, server_id: str, payload: MCPGatewayPolicy, actor: str = "creative-director") -> dict[str, Any]:
        now = now_iso()
        record = {
            "server_id": server_id,
            "application": payload.application,
            "operation_selector": payload.operation_selector,
            "allowed": json.dumps(sorted(set(payload.allowed_operations))),
            "denied": json.dumps(sorted(set(payload.denied_operations))),
            "write": json.dumps(sorted(set(payload.write_operations))),
            "approval": json.dumps(sorted(set(payload.approval_operations))),
            "scopes": json.dumps(sorted(set(payload.write_scopes))),
            "timeout": payload.timeout_seconds,
            "concurrency": payload.max_concurrency,
            "retries": payload.retry_limit,
            "rollback": payload.rollback_strategy,
            "enabled": int(payload.enabled),
            "created": now,
            "updated": now,
        }
        with self.engine.begin() as connection:
            if connection.execute(text("SELECT 1 FROM mcp_servers WHERE id=:id"), {"id": server_id}).first() is None:
                raise DomainError("MCP server not found", 404)
            connection.execute(
                text(
                    "INSERT INTO mcp_gateway_policies VALUES("
                    ":server_id,:application,:operation_selector,:allowed,:denied,:write,:approval,:scopes,"
                    ":timeout,:concurrency,:retries,:rollback,:enabled,:created,:updated) "
                    "ON CONFLICT(server_id) DO UPDATE SET application=:application,"
                    "operation_selector=:operation_selector,"
                    "allowed_operations_json=:allowed,denied_operations_json=:denied,write_operations_json=:write,"
                    "approval_operations_json=:approval,write_scopes_json=:scopes,timeout_seconds=:timeout,"
                    "max_concurrency=:concurrency,retry_limit=:retries,rollback_strategy=:rollback,enabled=:enabled,updated_at=:updated"
                ),
                record,
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events(actor,action,subject_kind,subject_id,before_json,after_json,created_at) "
                    "VALUES(:actor,'SET_POLICY','MCP_SERVER',:id,NULL,:after,:created)"
                ),
                {"actor": actor, "id": server_id, "after": json.dumps(record, sort_keys=True), "created": now},
            )
        return {**record, "enabled": bool(record["enabled"])}

    def list_invocations(self, server_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM mcp_invocations"
        params: dict[str, Any] = {}
        if server_id:
            query += " WHERE server_id=:server_id"
            params["server_id"] = server_id
        query += " ORDER BY created_at,id"
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(query), params).mappings()]

    def begin(self, server_id: str, request: MCPInvocationRequest) -> dict[str, Any]:
        invocation_id = f"mcpi_{uuid4().hex}"
        created = now_iso()
        with self.engine.begin() as connection:
            policy_row = connection.execute(
                text(
                    "SELECT p.*,s.bind_host FROM mcp_gateway_policies p "
                    "JOIN mcp_servers s ON s.id=p.server_id WHERE p.server_id=:id"
                ),
                {"id": server_id},
            ).mappings().first()
            if policy_row is None:
                raise DomainError("MCP gateway policy not found", 404)
            policy = dict(policy_row)
            operation = self._operation(policy["operation_selector"], request)
            reasons: list[str] = []
            if not policy["enabled"]:
                reasons.append("gateway policy is disabled")
            if policy["bind_host"] not in {"127.0.0.1", "localhost"}:
                reasons.append("server bind is not loopback")
            allowed = json.loads(policy["allowed_operations_json"])
            denied = json.loads(policy["denied_operations_json"])
            writes = json.loads(policy["write_operations_json"])
            approvals = json.loads(policy["approval_operations_json"])
            scopes = [Path(value).resolve(strict=False) for value in json.loads(policy["write_scopes_json"])]
            if self._matches(operation, denied):
                reasons.append("operation is explicitly denied")
            if not self._matches(operation, allowed):
                reasons.append("operation is not allow-listed")
            is_write = self._matches(operation, writes)
            workspace: Path | None = None
            if is_write:
                if not request.workspace_path:
                    reasons.append("write operation requires a workspace path")
                else:
                    workspace = Path(request.workspace_path).resolve(strict=False)
                    if not any(workspace.is_relative_to(scope) for scope in scopes):
                        reasons.append("workspace is outside the policy write scopes")
            approval_id = request.approval_id
            if self._matches(operation, approvals):
                if not approval_id:
                    reasons.append("operation requires explicit approval")
                else:
                    approval = connection.execute(
                        text(
                            "SELECT id FROM approvals WHERE id=:approval AND subject_kind='MCP_OPERATION' "
                            "AND subject_id=:subject AND decision='APPROVED'"
                        ),
                        {"approval": approval_id, "subject": approval_subject(server_id, operation)},
                    ).first()
                    if approval is None:
                        reasons.append("approval is missing, mismatched, or not approved")
            if operation in {"execute_blender_code", "python.execute", "execute_python"} and isinstance(
                request.arguments.get("code"), str
            ):
                try:
                    self._validate_code(request.arguments["code"], scopes)
                except DomainError as exc:
                    reasons.append(exc.message)
            running = connection.execute(
                text("SELECT COUNT(*) FROM mcp_invocations WHERE server_id=:id AND status='RUNNING'"),
                {"id": server_id},
            ).scalar_one()
            if running >= policy["max_concurrency"]:
                reasons.append("server concurrency limit reached")
            status = "DENIED" if reasons else "RUNNING"
            connection.execute(
                text(
                    "INSERT INTO mcp_invocations("
                    "id,server_id,operation,arguments_json,workspace_path,approval_id,status,actor,created_at"
                    ") "
                    "VALUES(:id,:server,:operation,:arguments,:workspace,:approval,:status,:actor,:created)"
                ),
                {
                    "id": invocation_id,
                    "server": server_id,
                    "operation": operation,
                    "arguments": json.dumps(self._sanitize_arguments(request.arguments), sort_keys=True),
                    "workspace": str(workspace) if workspace else request.workspace_path,
                    "approval": approval_id,
                    "status": status,
                    "actor": request.actor,
                    "created": created,
                },
            )
            evidence = {"operation": operation, "status": status, "reasons": reasons}
            connection.execute(
                text(
                    "INSERT INTO audit_events(actor,action,subject_kind,subject_id,before_json,after_json,created_at) "
                    "VALUES(:actor,:action,'MCP_INVOCATION',:id,NULL,:after,:created)"
                ),
                {
                    "actor": request.actor,
                    "action": "DENY" if reasons else "AUTHORIZE",
                    "id": invocation_id,
                    "after": json.dumps(evidence, sort_keys=True),
                    "created": created,
                },
            )
        if reasons:
            raise DomainError(f"MCP invocation denied: {'; '.join(reasons)}", 403)
        return {
            "id": invocation_id,
            "server_id": server_id,
            "operation": operation,
            "status": "RUNNING",
            "timeout_seconds": policy["timeout_seconds"],
            "retry_limit": policy["retry_limit"],
            "rollback_strategy": policy["rollback_strategy"],
        }

    def complete(self, invocation_id: str, payload: MCPInvocationCompletion) -> dict[str, Any]:
        completed = now_iso()
        with self.engine.begin() as connection:
            row = connection.execute(
                text("SELECT * FROM mcp_invocations WHERE id=:id"), {"id": invocation_id}
            ).mappings().first()
            if row is None:
                raise DomainError("MCP invocation not found", 404)
            if row["status"] != "RUNNING":
                raise DomainError("only a running invocation can be completed", 409)
            connection.execute(
                text(
                    "UPDATE mcp_invocations SET status=:status,attempt_count=:attempts,duration_ms=:duration,"
                    "result_summary_json=:summary,rollback_status=:rollback,error_code=:error,"
                    "completed_at=:completed WHERE id=:id"
                ),
                {
                    "status": payload.status,
                    "attempts": payload.attempt_count,
                    "duration": payload.duration_ms,
                    "summary": json.dumps(payload.result_summary, sort_keys=True),
                    "rollback": payload.rollback_status,
                    "error": payload.error_code,
                    "completed": completed,
                    "id": invocation_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events(actor,action,subject_kind,subject_id,before_json,after_json,created_at) "
                    "VALUES(:actor,:action,'MCP_INVOCATION',:id,NULL,:after,:created)"
                ),
                {
                    "actor": row["actor"],
                    "action": payload.status,
                    "id": invocation_id,
                    "after": payload.model_dump_json(),
                    "created": completed,
                },
            )
        return {"id": invocation_id, "status": payload.status, "completed_at": completed}

    def execute(
        self,
        server_id: str,
        request: MCPInvocationRequest,
        invoke: Callable[[], dict[str, Any]],
        rollback: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        decision = self.begin(server_id, request)
        with self._locks_guard:
            semaphore = self._locks.setdefault(server_id, threading.BoundedSemaphore(1))
        attempts = 0
        error_code: str | None = None
        last_error: Exception | None = None
        rollback_status: str | None = None
        try:
            with semaphore:
                for attempt in range(decision["retry_limit"] + 1):
                    attempts = attempt + 1
                    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-gateway")
                    future = executor.submit(invoke)
                    try:
                        result = future.result(timeout=decision["timeout_seconds"])
                        executor.shutdown(wait=True, cancel_futures=True)
                        duration = int((time.monotonic() - started) * 1000)
                        summary = {"keys": sorted(result), "ok": True}
                        self.complete(
                            decision["id"],
                            MCPInvocationCompletion(
                                status="SUCCEEDED",
                                attempt_count=attempts,
                                duration_ms=duration,
                                result_summary=summary,
                            ),
                        )
                        return {"invocation_id": decision["id"], "result": result}
                    except FutureTimeout:
                        error_code = "TIMEOUT"
                        last_error = FutureTimeout(
                            f"MCP adapter exceeded {decision['timeout_seconds']} seconds"
                        )
                        future.cancel()
                        executor.shutdown(wait=False, cancel_futures=True)
                    except Exception as exc:
                        error_code = "ADAPTER_ERROR"
                        last_error = exc
                        executor.shutdown(wait=True, cancel_futures=True)
                    if attempt < decision["retry_limit"]:
                        continue
            if rollback:
                try:
                    rollback()
                    rollback_status = "SUCCEEDED"
                except Exception:
                    rollback_status = "FAILED"
            duration = int((time.monotonic() - started) * 1000)
            self.complete(
                decision["id"],
                MCPInvocationCompletion(
                    status="FAILED",
                    attempt_count=attempts,
                    duration_ms=duration,
                    result_summary={"ok": False},
                    rollback_status=rollback_status,
                    error_code=error_code,
                ),
            )
            raise DomainError(f"MCP adapter failed after {attempts} attempt(s)", 502) from last_error
        except Exception:
            raise
