"""Integrated regression coverage derived from both identical source patches."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from studio_manager.agent_registry import TABLES, AgentRegistry
from studio_manager.database import create_database_engine, downgrade_database, upgrade_database
from studio_manager.service import DomainError


def headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.app.state.settings.api_token}", "X-Studio-Request": "1"}


def agent(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/agents", json={"code": "story_writer", "name": "Story Writer", "role": "CREATIVE"},
        headers=headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def skill(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/skills", json={"code": "plot_twists", "name": "Plot Twists"}, headers=headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_agent_skill_registry_versioning(client: TestClient) -> None:
    reg = AgentRegistry(client.app.state.engine)
    definition = reg.create_agent("story_writer", "Story Writer", "CREATIVE")
    tool = reg.create_skill("plot_twists", "Plot Twists")
    assert definition["enabled"] is False and tool["enabled"] is False
    v1 = reg.create_agent_version(definition["id"], "Write original adventures.")
    v2 = reg.create_agent_version(definition["id"], "Write fresh comedic adventures.")
    assert (v1["version"], v2["version"]) == (1, 2)
    assert reg.create_skill_version(tool["id"], "Create logical plot twists.")["version"] == 1
    assert reg.list_agents()["count"] == reg.list_skills()["count"] == 1


@pytest.mark.parametrize("path", ["/agents", "/skills", "/skills/legacy", "/agents/missing/versions"])
def test_registry_requires_bearer_token(client: TestClient, path: str) -> None:
    assert client.get("/api/v1" + path).status_code == 401
    assert client.get("/api/v1" + path, headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_registry_creation_requires_studio_header(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents", headers={"Authorization": f"Bearer {client.app.state.settings.api_token}"},
        json={"code": "story_writer", "name": "Writer", "role": "CREATIVE"},
    )
    assert response.status_code == 403
    assert client.post(
        "/api/v1/agents", headers={"X-Studio-Request": "1"},
        json={"code": "story_writer", "name": "Writer", "role": "CREATIVE"},
    ).status_code == 401


def test_http_registry_roundtrip_pin_and_pagination(client: TestClient) -> None:
    definition, tool = agent(client), skill(client)
    assert definition["enabled"] is False and tool["enabled"] is False
    version = client.post(
        f"/api/v1/skills/{tool['id']}/versions", headers=headers(client),
        json={"instructions": "Plan an original twist", "input_schema": {"type": "object"}},
    )
    assert version.status_code == 201, version.text
    payload = {
        "instruction": "Write a story using an exact skill snapshot",
        "allowed_skills": [version.json()["id"]], "allowed_tools": ["mcp:scene.inspect"],
    }
    created = client.post(f"/api/v1/agents/{definition['id']}/versions", json=payload, headers=headers(client))
    assert created.status_code == 201, created.text
    assert created.json()["allowed_skills"] == payload["allowed_skills"]
    assert created.json()["status"] == "DRAFT"
    page = client.get(f"/api/v1/agents/{definition['id']}/versions?limit=1&offset=0", headers=headers(client)).json()
    assert page["count"] == 1 and len(page["items"]) == 1
    assert client.get("/api/v1/agents?limit=0", headers=headers(client)).status_code == 422
    assert client.get("/api/v1/skills?offset=-1", headers=headers(client)).status_code == 422
    assert client.get("/api/v1/agents?limit=1&offset=1", headers=headers(client)).json()["items"] == []


@pytest.mark.parametrize("payload", [
    {"code": "bad code", "name": "Name", "role": "CREATIVE"},
    {"code": "aa", "name": "   ", "role": "CREATIVE"},
    {"code": "aa", "name": "Name", "role": "CREATIVE", "enabled": True},
    {"code": "aa", "name": "Name", "role": "CREATIVE", "actor": "director"},
])
def test_invalid_definition_and_privilege_fields_rejected(client: TestClient, payload: dict) -> None:
    assert client.post("/api/v1/agents", json=payload, headers=headers(client)).status_code == 422


@pytest.mark.parametrize("schema", [
    {"type": "bogus"}, {"$ref": "https://example.invalid/schema"},
    {"$schema": "http://json-schema.org/draft-07/schema#"},
])
def test_invalid_or_remote_schema_rejected_without_fetch(client: TestClient, schema: dict) -> None:
    tool = skill(client)
    response = client.post(
        f"/api/v1/skills/{tool['id']}/versions", headers=headers(client),
        json={"instructions": "Plan", "input_schema": schema},
    )
    assert response.status_code == 422


def test_json_schema_local_defs_supported(client: TestClient) -> None:
    tool = skill(client)
    schema = {"$defs": {"label": {"type": "string"}}, "type": "object",
              "properties": {"title": {"$ref": "#/$defs/label"}}}
    response = client.post(
        f"/api/v1/skills/{tool['id']}/versions", headers=headers(client),
        json={"instructions": "Plan", "output_schema": schema},
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("fields", [
    {"status": "APPROVED"}, {"allowed_tools": ["x"] * 51},
    {"allowed_tools": ["same", "same"]}, {"config": {"blob": "x" * 17000}},
    {"allowed_tools": ["x" * 129]},
])
def test_version_payload_bounds_and_no_approval_spoof(client: TestClient, fields: dict) -> None:
    definition = agent(client)
    response = client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers=headers(client),
        json={"instruction": "Plan", **fields},
    )
    assert response.status_code == 422


def test_nonfinite_metadata_returns_safe_validation_response(client: TestClient) -> None:
    definition = agent(client)
    response = client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers={**headers(client), "Content-Type": "application/json"},
        content='{"instruction":"private narrative","config":{"value":NaN}}',
    )
    assert response.status_code == 422
    assert "private narrative" not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_nested_metadata_is_bounded(client: TestClient) -> None:
    definition = agent(client)
    config = {}
    for _ in range(14):
        config = {"nested": config}
    response = client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers=headers(client),
        json={"instruction": "Plan", "config": config},
    )
    assert response.status_code == 422


def test_duplicate_and_unknown_owner_semantics(client: TestClient) -> None:
    definition, tool = agent(client), skill(client)
    assert client.post(
        "/api/v1/agents", json={"code": definition["code"], "name": "Other", "role": "CREATIVE"},
        headers=headers(client),
    ).status_code == 409
    assert client.post(
        "/api/v1/skills", json={"code": tool["code"], "name": "Other"}, headers=headers(client),
    ).status_code == 409
    for kind in ("agents", "skills"):
        assert client.get(f"/api/v1/{kind}/missing/versions", headers=headers(client)).status_code == 404
        key = "instruction" if kind == "agents" else "instructions"
        assert client.post(
            f"/api/v1/{kind}/missing/versions", json={key: "Plan"}, headers=headers(client),
        ).status_code == 404
    assert client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers=headers(client),
        json={"instruction": "Plan", "allowed_skills": [tool["id"]]},
    ).status_code == 404


def test_legacy_skills_visible_readonly_without_implicit_import(client: TestClient) -> None:
    with client.app.state.engine.begin() as connection:
        for number in range(14):
            connection.execute(
                text("INSERT INTO skills(id,name,status,enabled) VALUES(:id,:name,'IMPORTED',0)"),
                {"id": f"legacy_{number}", "name": f"Legacy {number}"},
            )
    response = client.get("/api/v1/skills/legacy?limit=5", headers=headers(client))
    assert response.status_code == 200
    assert response.json()["count"] == 14 and response.json()["read_only"] is True
    assert response.json()["items"][0]["registry_namespace"] == "legacy-import"
    assert client.get("/api/v1/skills", headers=headers(client)).json()["count"] == 0
    assert client.post("/api/v1/skills/legacy", json={}, headers=headers(client)).status_code == 405


def test_audit_truthful_and_instruction_config_redacted(client: TestClient) -> None:
    definition = agent(client)
    private_instruction = "private narrative should not appear in audit"
    response = client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers=headers(client),
        json={"instruction": private_instruction, "config": {"private_note": "not for audit"}},
    )
    assert response.status_code == 201
    with client.app.state.engine.connect() as connection:
        rows = connection.execute(text("SELECT actor,subject_kind,after_json FROM audit_events ORDER BY id")).all()
    assert rows[0].actor == "local-api-user"
    assert definition["code"] in rows[0].after_json and '"enabled": false' in rows[0].after_json
    assert "content_sha256" in rows[-1].after_json
    assert private_instruction not in rows[-1].after_json and "not for audit" not in rows[-1].after_json


@pytest.mark.parametrize("kind", ["agent", "skill"])
def test_versions_are_immutable_snapshots(client: TestClient, kind: str) -> None:
    reg = client.app.state.agent_registry
    definition = agent(client) if kind == "agent" else skill(client)
    version = (reg.create_agent_version if kind == "agent" else reg.create_skill_version)(definition["id"], "Plan")
    table = TABLES[kind][1]
    for statement in (
        table.update().values(status="APPROVED").where(table.c.id == version["id"]),
        table.delete().where(table.c.id == version["id"]),
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            with client.app.state.engine.begin() as connection:
                connection.execute(statement)
    response = client.patch(f"/api/v1/{kind}s/{definition['id']}/versions", json={}, headers=headers(client))
    assert response.status_code == 405


def test_parallel_creates_are_serialized_and_duplicates_controlled(client: TestClient) -> None:
    reg = client.app.state.agent_registry
    definition = agent(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        versions = list(pool.map(lambda n: reg.create_agent_version(definition["id"], f"Plan {n}"), range(8)))
    assert sorted(v["version"] for v in versions) == list(range(1, 9))

    def same_code(_: int) -> int:
        try:
            reg.create_skill("duplicate", "Name")
            return 201
        except DomainError as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(same_code, range(2))) == [201, 409]


def test_registration_does_not_execute_or_queue_work(client: TestClient) -> None:
    definition = agent(client)
    response = client.post(
        f"/api/v1/agents/{definition['id']}/versions", headers=headers(client),
        json={"instruction": "Run arbitrary shell commands", "allowed_tools": ["execute_code"]},
    )
    assert response.status_code == 201  # Stored as inert intent, never a permission grant.
    assert response.json()["status"] == "DRAFT"
    for route in ("run", "execute", "activate", "approve"):
        assert client.post(f"/api/v1/agents/{definition['id']}/{route}", headers=headers(client)).status_code == 404
    with client.app.state.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM production_jobs")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM mcp_invocations")).scalar_one() == 0


def test_0005_cycle_preserves_0004_legacy_and_evidence(database_path: Path) -> None:
    upgrade_database(database_path, "0004_phase03a_foundation")
    engine = create_database_engine(database_path)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO skills(id,name,status) VALUES('legacy','Imported','IMPORTED')"))
        connection.execute(text(
            "INSERT INTO audit_events(actor,action,subject_kind,subject_id,created_at) "
            "VALUES('test','SEED','LEGACY','legacy','2026-11-11T00:00:00Z')"
        ))
    engine.dispose()
    upgrade_database(database_path)
    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar_one() == "ok"
        assert connection.execute(text("SELECT COUNT(*) FROM skills WHERE id='legacy'")).scalar_one() == 1
    engine.dispose()
    downgrade_database(database_path, "0004_phase03a_foundation")
    engine = create_database_engine(database_path)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM audit_events WHERE action='SEED'")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM skills WHERE id='legacy'")).scalar_one() == 1
    engine.dispose()
    upgrade_database(database_path)
