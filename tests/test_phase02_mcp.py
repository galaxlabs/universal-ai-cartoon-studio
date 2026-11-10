from __future__ import annotations

from fastapi.testclient import TestClient

HEADERS = {"X-Studio-Request": "1"}


def register(client: TestClient, **overrides):
    payload = {
        "name": "blender-readonly",
        "source_url": "https://github.com/example/blender-readonly",
        "version": "1.0.0",
        "license": "MIT",
        "bind_host": "127.0.0.1",
        "permissions": ["read_scene"],
    }
    payload.update(overrides)
    return client.post("/api/mcp/servers", json=payload, headers=HEADERS)


def test_registry_starts_empty_and_activation_is_not_exposed(client: TestClient) -> None:
    body = client.get("/api/mcp/servers").json()
    assert body["servers"] == []
    assert body["activation_exposed"] is False


def test_register_creates_disabled_loopback_entry(client: TestClient) -> None:
    response = register(client)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["enabled"] == 0
    assert created["status"] == "REGISTERED"
    assert created["bind_host"] == "127.0.0.1"

    listed = client.get("/api/mcp/servers").json()["servers"]
    assert [item["name"] for item in listed] == ["blender-readonly"]


def test_duplicate_name_is_rejected(client: TestClient) -> None:
    assert register(client).status_code == 201
    duplicate = register(client)
    assert duplicate.status_code == 409


def test_non_loopback_bind_is_rejected(client: TestClient) -> None:
    response = register(client, bind_host="0.0.0.0")  # noqa: S104 - asserting rejection
    assert response.status_code == 422


def test_https_source_is_required(client: TestClient) -> None:
    response = register(client, source_url="http://example.com/repo")
    assert response.status_code == 422


def test_execute_code_permission_blocks_activation(client: TestClient) -> None:
    created = register(client, name="blender-broad", permissions=["read_scene", "execute_code"]).json()
    check = client.get(f"/api/mcp/servers/{created['id']}/activation-check").json()
    assert check["would_enable"] is False
    assert any("execute_code" in reason for reason in check["reasons"])
    assert "not implemented" in check["note"]


def test_unknown_server_returns_404(client: TestClient) -> None:
    response = client.get("/api/mcp/servers/mcp_missing/activation-check")
    assert response.status_code == 404


def test_read_only_loopback_server_would_enable(client: TestClient) -> None:
    created = register(client).json()
    check = client.get(f"/api/mcp/servers/{created['id']}/activation-check").json()
    assert check["would_enable"] is True
    assert check["reasons"] == []
    assert check["active_servers"] == 0


def test_registration_requires_studio_header(client: TestClient) -> None:
    response = client.post(
        "/api/mcp/servers",
        json={
            "name": "no-header",
            "version": "1",
            "license": "MIT",
            "bind_host": "127.0.0.1",
            "permissions": ["read_scene"],
        },
    )
    assert response.status_code == 403
