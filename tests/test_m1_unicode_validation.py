"""M1: reject invalid nested Unicode before any version/audit transaction."""

import json
from itertools import product
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from studio_manager.agent_models import StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion
from studio_manager.config import Settings
from studio_manager.main import create_app
from studio_manager.models import AuditEvent

TARGETS = ("config", "input_schema", "output_schema")
PLACEMENTS = ("object_value", "nested_value", "array_value", "array_object", "object_key", "nested_key")
INVALID_CASES = list(product(TARGETS, PLACEMENTS, (0xD800, 0xDBFF, 0xDC00, 0xDFFF)))
VALID_TEXT = "اردو اور emoji: لومڑی 🦊، راکٹ 🚀، 世界، e\u0301"
VALID_METADATA = {"اردو 🔑": VALID_TEXT, "nested": [{"نام": "لومڑی 🦊"}, "🚀", 42, True, None]}


@pytest.fixture
def m1_client(database_path):
    settings = Settings(project_root=database_path.parent, database_path=database_path, test_mode=True)
    # An actual HTTP500 must become a failing status assertion, not an exception
    # escaping the client before the persisted-row regression can be checked.
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def headers(client):
    return {"Authorization": f"Bearer {client.app.state.settings.api_token}",
            "X-Studio-Request": "1", "Content-Type": "application/json"}


def metadata(target, content):
    return content if target == "config" else {"type": "object", "examples": [content]}


def version_payload(target, content):
    instruction_key = "instruction" if target == "config" else "instructions"
    return {instruction_key: VALID_TEXT, target: metadata(target, content)}


def owner_path(client, target):
    if target == "config":
        kind = "agents"
        definition = {"code": "unicode_agent", "name": "اردو لومڑی 🦊", "role": "QA"}
    else:
        kind = "skills"
        definition = {"code": "unicode_skill", "name": "اردو مہارت 🚀"}
    created = client.post("/api/v1/" + kind, headers=headers(client), json=definition)
    assert created.status_code == 201, created.text
    return f"/api/v1/{kind}/{created.json()['id']}/versions"


def snapshot(client):
    tables = (StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion, AuditEvent)
    with client.app.state.engine.connect() as connection:
        return {
            model.__tablename__: [dict(r) for r in connection.execute(
                select(model.__table__).order_by(model.__table__.c.id)
            ).mappings()]
            for model in tables
        }


def invalid_metadata(placement, codepoint):
    bad = "prefix" + chr(codepoint) + "suffix"
    return {
        "object_value": {"note": bad},
        "nested_value": {"outer": {"note": bad}},
        "array_value": {"items": ["safe", bad]},
        "array_object": {"items": [{"note": bad}]},
        "object_key": {bad: "safe"},
        "nested_key": {"outer": [{bad: "safe"}]},
    }[placement]


@pytest.mark.parametrize(
    ("target", "placement", "codepoint"), INVALID_CASES,
    ids=[f"{target}-{placement}-{codepoint:X}" for target, placement, codepoint in INVALID_CASES],
)
def test_invalid_unicode_metadata_rejected(m1_client, target, placement, codepoint):
    client = m1_client
    path = owner_path(client, target)
    first = client.post(path, headers=headers(client), json=version_payload(target, VALID_METADATA))
    assert first.status_code == 201, first.text
    before = snapshot(client)
    # ASCII wire escapes let the invalid scalar reach the server; do not let the
    # test client's own UTF-8 encoder reject it before the real validation path.
    response = client.post(
        path, headers=headers(client),
        content=json.dumps(version_payload(target, invalid_metadata(placement, codepoint)), ensure_ascii=True),
    )
    assert response.status_code == 422, response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert snapshot(client) == before  # Definitions, versions AND audit rows unchanged.
    listing = client.get(path, headers=headers(client))
    assert listing.status_code == 200, listing.text
    assert listing.json()["count"] == 1
    assert listing.json()["items"][0][target] == metadata(target, VALID_METADATA)
    second = client.post(path, headers=headers(client), json=version_payload(target, VALID_METADATA))
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 2  # Rejection must not consume a version.


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("escaped", [False, True], ids=["utf8-wire", "escaped-wire"])
def test_valid_international_unicode_roundtrips(m1_client, target, escaped):
    client = m1_client
    path = owner_path(client, target)
    response = client.post(
        path, headers=headers(client),
        content=json.dumps(version_payload(target, VALID_METADATA), ensure_ascii=escaped).encode("utf-8"),
    )
    assert response.status_code == 201, response.text
    assert response.json()[target] == metadata(target, VALID_METADATA)
    key = "instruction" if target == "config" else "instructions"
    assert response.json()[key] == VALID_TEXT
    listing = client.get(path, headers=headers(client))
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0][target] == metadata(target, VALID_METADATA)


@pytest.mark.parametrize("target", TARGETS)
def test_direct_service_validation_precedes_transaction(m1_client, target, monkeypatch):
    client = m1_client
    owner = owner_path(client, target).split("/")[-2]
    registry = client.app.state.agent_registry
    before = snapshot(client)
    write = Mock(side_effect=AssertionError("validation must precede transaction"))
    monkeypatch.setattr(registry, "_write", write)
    with pytest.raises(ValidationError):
        if target == "config":
            registry.create_agent_version(owner, "Plan", config={"nested": [{chr(0xD800): "safe"}]})
        else:
            registry.create_skill_version(
                owner, "Plan", **{target: {"type": "object", "examples": [{"note": chr(0xDFFF)}]}},
            )
    write.assert_not_called()
    assert snapshot(client) == before
