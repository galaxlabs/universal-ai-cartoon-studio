from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio_manager.config import PROJECT_ROOT
from studio_manager.mcp_gateway import MCPGateway, MCPInvocationRequest, approval_subject
from studio_manager.service import DomainError

HEADERS = {"X-Studio-Request": "1"}


@pytest.fixture
def development_root() -> Path:
    path = PROJECT_ROOT / "storage" / "20_TEMP" / "pytest" / "mcp-gateway"
    path.mkdir(parents=True, exist_ok=True)
    return path


def register(client: TestClient, name: str = "pinwright") -> dict:
    response = client.post(
        "/api/mcp/servers",
        headers=HEADERS,
        json={
            "name": name,
            "source_url": "https://github.com/example/reviewed",
            "version": "1.0.0",
            "license": "MIT",
            "bind_host": "127.0.0.1",
            "permissions": ["read_scene", "write_scene"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def set_policy(client: TestClient, server_id: str, workspace: Path, **overrides) -> dict:
    payload = {
        "application": "UNREAL",
        "operation_selector": "method",
        "allowed_operations": ["system.*", "actor.*", "python.execute"],
        "denied_operations": ["python.execute", "system.editor_build"],
        "write_operations": ["actor.*"],
        "approval_operations": ["actor.*"],
        "write_scopes": [str(workspace)],
        "timeout_seconds": 5,
        "max_concurrency": 1,
        "retry_limit": 1,
        "rollback_strategy": "delete_isolated_output",
        "enabled": True,
    }
    payload.update(overrides)
    response = client.put(f"/api/mcp/servers/{server_id}/gateway-policy", headers=HEADERS, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client: TestClient, server_id: str, operation: str) -> str:
    response = client.post(
        "/api/approvals",
        headers=HEADERS,
        json={
            "subject_kind": "MCP_OPERATION",
            "subject_id": approval_subject(server_id, operation),
            "decision": "APPROVED",
            "decided_by": "creative-director",
            "notes": "isolated integration test",
            "evidence": {"scope": "test"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_nested_method_is_denied_even_when_generic_tool_is_call(client: TestClient, development_root: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root)
    response = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={"tool_name": "call", "arguments": {"method": "python.execute", "code": "print('x')"}},
    )
    assert response.status_code == 403
    assert "explicitly denied" in response.json()["error"]
    logged = client.get("/api/mcp/invocations").json()["invocations"]
    assert logged[0]["operation"] == "python.execute"
    assert logged[0]["status"] == "DENIED"
    assert "print('x')" not in logged[0]["arguments_json"]


def test_write_requires_matching_approval_and_managed_scope(client: TestClient, development_root: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root)
    approval = approve(client, server["id"], "actor.spawn")
    response = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={
            "tool_name": "call",
            "arguments": {"method": "actor.spawn", "class": "CineCameraActor"},
            "workspace_path": str(development_root / "ue-test"),
            "approval_id": approval,
        },
    )
    assert response.status_code == 201, response.text
    invocation = response.json()
    completed = client.post(
        f"/api/mcp/invocations/{invocation['id']}/complete",
        headers=HEADERS,
        json={"status": "SUCCEEDED", "attempt_count": 1, "duration_ms": 12, "result_summary": {"ok": True}},
    )
    assert completed.status_code == 200


def test_write_outside_scope_is_denied(client: TestClient, development_root: Path, tmp_path: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root)
    approval = approve(client, server["id"], "actor.spawn")
    response = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={
            "tool_name": "call",
            "arguments": {"method": "actor.spawn"},
            "workspace_path": str(tmp_path),
            "approval_id": approval,
        },
    )
    assert response.status_code == 403
    assert "outside" in response.json()["error"]


def test_safe_blender_code_rejects_process_and_external_paths(client: TestClient, development_root: Path) -> None:
    server = register(client, "blender")
    set_policy(
        client,
        server["id"],
        development_root,
        application="BLENDER",
        operation_selector="tool",
        allowed_operations=["get_scene_info", "execute_blender_code"],
        denied_operations=[],
        write_operations=["execute_blender_code"],
        approval_operations=["execute_blender_code"],
    )
    approval = approve(client, server["id"], "execute_blender_code")
    response = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={
            "tool_name": "execute_blender_code",
            "arguments": {"code": "import subprocess\nsubprocess.run(['whoami'])"},
            "workspace_path": str(development_root / "blender-test"),
            "approval_id": approval,
        },
    )
    assert response.status_code == 403
    assert "denied module" in response.json()["error"]


def test_concurrency_limit_blocks_second_running_call(client: TestClient, development_root: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root, approval_operations=[])
    first = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={
            "tool_name": "call",
            "arguments": {"method": "actor.spawn"},
            "workspace_path": str(development_root / "ue-test"),
        },
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/mcp/servers/{server['id']}/invocations",
        headers=HEADERS,
        json={
            "tool_name": "call",
            "arguments": {"method": "actor.spawn"},
            "workspace_path": str(development_root / "ue-test"),
        },
    )
    assert second.status_code == 403
    assert "concurrency" in second.json()["error"]


def test_internal_executor_retries_and_records_success(client: TestClient, development_root: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root, approval_operations=[])
    gateway: MCPGateway = client.app.state.mcp_gateway
    calls = 0

    def flaky() -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient")
        return {"ok": True, "object": "Cube"}

    result = gateway.execute(
        server["id"],
        MCPInvocationRequest(
            tool_name="call",
            arguments={"method": "actor.spawn"},
            workspace_path=str(development_root / "ue-test"),
        ),
        flaky,
    )
    assert calls == 2
    assert result["result"]["object"] == "Cube"
    invocation = gateway.list_invocations(server["id"])[0]
    assert invocation["status"] == "SUCCEEDED"
    assert invocation["attempt_count"] == 2


def test_internal_executor_rolls_back_after_final_failure(client: TestClient, development_root: Path) -> None:
    server = register(client)
    set_policy(client, server["id"], development_root, approval_operations=[], retry_limit=0)
    gateway: MCPGateway = client.app.state.mcp_gateway
    rolled_back = False

    def fail() -> dict[str, object]:
        raise RuntimeError("permanent")

    def rollback() -> None:
        nonlocal rolled_back
        rolled_back = True

    try:
        gateway.execute(
            server["id"],
            MCPInvocationRequest(
                tool_name="call",
                arguments={"method": "actor.spawn"},
                workspace_path=str(development_root / "ue-test"),
            ),
            fail,
            rollback,
        )
    except DomainError as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError("gateway should surface adapter failure")
    assert rolled_back is True
    invocation = gateway.list_invocations(server["id"])[0]
    assert invocation["status"] == "FAILED"
    assert invocation["rollback_status"] == "SUCCEEDED"
