"""L1: registry offsets must fit SQLite's nonnegative signed64-bit range."""

from functools import partial

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from studio_manager.agent_models import StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion
from studio_manager.config import Settings
from studio_manager.main import create_app
from studio_manager.models import AuditEvent
from studio_manager.service import DomainError

EXPECTED_MAX = (1 << 63) - 1
KINDS = ("agents", "skills", "legacy", "agent_versions", "skill_versions")
INVALID = (-1, EXPECTED_MAX + 1, 1 << 80, 10 ** 100)
INVALID_IDS = ("negative", "overflow", "large", "huge")


@pytest.fixture
def l1_client(database_path):
    settings = Settings(project_root=database_path.parent, database_path=database_path, test_mode=True)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def headers(client):
    return {"Authorization": "Bearer " + client.app.state.settings.api_token, "X-Studio-Request": "1"}


@pytest.fixture
def listings(l1_client):
    reg = l1_client.app.state.agent_registry
    agents = [reg.create_agent("agent_" + label, "Agent " + label, "QA") for label in ("a", "b")]
    skills = [reg.create_skill("skill_" + label, "Skill " + label) for label in ("a", "b")]
    agent_versions = [reg.create_agent_version(agents[0]["id"], "Plan " + label) for label in ("a", "b")]
    skill_versions = [reg.create_skill_version(skills[0]["id"], "Plan " + label) for label in ("a", "b")]
    with l1_client.app.state.engine.begin() as connection:
        for number in range(2):
            connection.execute(text("INSERT INTO skills(id,name,status) VALUES(:id,:name,'IMPORTED')"),
                               {"id": f"legacy_{number}", "name": f"Legacy {number}"})
    return {
        "agents": ("/api/v1/agents", reg.list_agents, [r["id"] for r in agents]),
        "skills": ("/api/v1/skills", reg.list_skills, [r["id"] for r in skills]),
        "legacy": ("/api/v1/skills/legacy", reg.list_legacy_skills, ["legacy_0", "legacy_1"]),
        "agent_versions": (f"/api/v1/agents/{agents[0]['id']}/versions",
                           partial(reg.list_versions, "agent", agents[0]["id"]), [r["id"] for r in agent_versions]),
        "skill_versions": (f"/api/v1/skills/{skills[0]['id']}/versions",
                           partial(reg.list_versions, "skill", skills[0]["id"]), [r["id"] for r in skill_versions]),
    }


def snapshot(client, connect=None):
    with (connect or client.app.state.engine.connect)() as connection:
        result = {
            model.__tablename__: [dict(r) for r in connection.execute(
                select(model.__table__).order_by(model.__table__.c.id)
            ).mappings()]
            for model in (StudioAgent, StudioAgentVersion, StudioSkill, StudioSkillVersion, AuditEvent)
        }
        result["legacy_skills"] = [
            dict(r) for r in connection.execute(text("SELECT * FROM skills ORDER BY id")).mappings()
        ]
        return result


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("offset", INVALID, ids=INVALID_IDS)
def test_registry_rejects_out_of_range_offset(l1_client, listings, kind, offset):
    before = snapshot(l1_client)
    path = listings[kind][0]
    response = l1_client.get(path, params={"offset": str(offset)}, headers=headers(l1_client))
    print({"kind": kind, "offset": offset, "http": response.status_code})
    assert response.status_code == 422, response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert snapshot(l1_client) == before


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("offset", (0, 1, EXPECTED_MAX - 1, EXPECTED_MAX), ids=("zero", "one", "max-minus-one", "max"))
def test_valid_offset_boundaries_work_in_api_and_service(l1_client, listings, kind, offset):
    path, direct, expected = listings[kind]
    before = snapshot(l1_client)
    response = l1_client.get(path, params={"offset": str(offset), "limit": "100"}, headers=headers(l1_client))
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["offset"] == offset and page["count"] == 2
    assert [r["id"] for r in page["items"]] == expected[offset:]
    assert direct(limit=100, offset=offset) == page
    assert snapshot(l1_client) == before


@pytest.mark.parametrize("kind", KINDS)
def test_normal_pagination_is_preserved(l1_client, listings, kind):
    path, direct, expected = listings[kind]
    first = l1_client.get(path, params={"limit": 1, "offset": 0}, headers=headers(l1_client)).json()
    second = l1_client.get(path, params={"limit": 1, "offset": 1}, headers=headers(l1_client)).json()
    assert first["count"] == second["count"] == 2
    assert [r["id"] for r in first["items"]] == expected[:1]
    assert [r["id"] for r in second["items"]] == expected[1:]
    assert direct(limit=1, offset=1) == second


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("offset", INVALID, ids=INVALID_IDS)
def test_direct_service_invalid_offsets_rejected_before_sql(l1_client, listings, kind, offset, monkeypatch):
    from unittest.mock import Mock

    before = snapshot(l1_client)
    original = l1_client.app.state.engine.connect
    connect = Mock(side_effect=AssertionError("invalid offsets must not reach SQL"))
    monkeypatch.setattr(l1_client.app.state.engine, "connect", connect)
    with pytest.raises(DomainError) as error:
        listings[kind][1](offset=offset)
    assert error.value.status_code == 422
    connect.assert_not_called()
    assert snapshot(l1_client, connect=original) == before


@pytest.mark.parametrize("kind", KINDS)
def test_api_overflow_is_rejected_before_listing_sql(l1_client, listings, kind, monkeypatch):
    from unittest.mock import Mock

    original = l1_client.app.state.engine.connect
    connect = Mock(side_effect=AssertionError("overflow query must not run"))
    monkeypatch.setattr(l1_client.app.state.engine, "connect", connect)
    response = l1_client.get(listings[kind][0], params={"offset": str(EXPECTED_MAX + 1)}, headers=headers(l1_client))
    assert response.status_code == 422
    connect.assert_not_called()
    # The test's own integrity read is deliberately outside the mocked API path.
    assert snapshot(l1_client, connect=original)["studio_agents"]


def test_shared_maximum_is_exact_sqlite_signed_limit():
    from studio_manager.agent_registry import MAX_REGISTRY_OFFSET

    assert MAX_REGISTRY_OFFSET == EXPECTED_MAX == 9223372036854775807


def test_m4_authentication_still_precedes_invalid_offset_query(l1_client):
    before = snapshot(l1_client)
    response = l1_client.get("/api/v1/agents", params={"offset": str(EXPECTED_MAX + 1)})
    assert response.status_code == 401
    assert snapshot(l1_client) == before
