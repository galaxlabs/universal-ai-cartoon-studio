"""H1 regression: approval authority comes from authentication, never request identity."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from studio_manager.config import PROJECT_ROOT
from studio_manager.contracts import JobCreate, JobTransition, ProjectCreate
from studio_manager.service import DomainError, StudioService


def headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.app.state.settings.api_token}", "X-Studio-Request": "1"}


def payload() -> dict[str, str]:
    return {"subject_kind": "MCP_OPERATION", "subject_id": "h1_synthetic_review",
            "decision": "APPROVED", "decided_by": "forged-director"}


def counts(client: TestClient) -> tuple[int, int, int]:
    with client.app.state.engine.connect() as connection:
        row = connection.execute(text(
            "SELECT (SELECT COUNT(*) FROM approvals), (SELECT COUNT(*) FROM audit_events), "
            "(SELECT COUNT(*) FROM job_events)"
        )).one()
    return tuple(row)


def pending_job(client: TestClient, *, pending: bool = True) -> dict:
    service = client.app.state.service
    project = service.create_project(ProjectCreate(name="H1 isolated project"))
    job = service.create_job(JobCreate(
        project_id=project["id"], job_type="H1_METADATA_ONLY", requested_by="fixture",
        workspace_path=str(PROJECT_ROOT / "storage" / "20_TEMP" / "h1-unused-workspace"),
    ))
    if pending:
        for state in ("QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL"):
            job = service.transition_job(job["id"], JobTransition(target_status=state, actor="fixture"))
    return job


def assert_decision_actor(client: TestClient, subject_id: str) -> None:
    with client.app.state.engine.connect() as connection:
        approval = connection.execute(
            text("SELECT * FROM approvals WHERE subject_id=:id"), {"id": subject_id},
        ).mappings().one()
        event = connection.execute(
            text("SELECT * FROM audit_events WHERE action='DECIDE' AND subject_id=:id"), {"id": subject_id},
        ).mappings().one()
    assert approval["decided_by"] == event["actor"] == "local-api-user"
    assert json.loads(event["after_json"])["decided_by"] == "local-api-user"
    assert json.loads(event["after_json"])["id"] == approval["id"]


@pytest.mark.parametrize("authorization", [None, "Bearer incorrect", "Basic invalid"])
def test_unauthenticated_legacy_approval_has_no_side_effects(client: TestClient, authorization: str | None) -> None:
    before = counts(client)
    supplied = {"X-Studio-Request": "1"}
    if authorization is not None:
        supplied["Authorization"] = authorization
    response = client.post("/api/approvals", json=payload(), headers=supplied)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert counts(client) == before


@pytest.mark.parametrize("route", ["/api/approvals", "/api/v1/approvals"])
def test_authenticated_api_identity_is_trusted(client: TestClient, route: str) -> None:
    response = client.post(route, json=payload(), headers=headers(client))
    assert response.status_code == 201, response.text
    assert response.json()["decided_by"] == "local-api-user"
    assert_decision_actor(client, payload()["subject_id"])


def test_authenticated_approval_still_requires_intent_header(client: TestClient) -> None:
    before = counts(client)
    response = client.post(
        "/api/approvals", json=payload(),
        headers={"Authorization": headers(client)["Authorization"]},
    )
    assert response.status_code == 403
    assert counts(client) == before


@pytest.mark.parametrize("credential", [None, "invalid-token"])
def test_ui_approval_requires_authentication(client: TestClient, credential: str | None) -> None:
    job = pending_job(client)
    before = counts(client)
    data = {"subject_id": job["id"], "decision": "APPROVED", "decided_by": "forged-director"}
    if credential is not None:
        data["approval_token"] = credential
    response = client.post("/ui/approvals", data=data, headers={"X-Studio-Request": "1"})
    assert response.status_code == 401
    assert counts(client) == before


@pytest.mark.parametrize("credential_source", ["bearer", "form"])
def test_authenticated_ui_approval_preserves_job_audit_identity(client: TestClient, credential_source: str) -> None:
    job = pending_job(client)
    data = {"subject_id": job["id"], "decision": "APPROVED", "decided_by": "forged-director"}
    supplied = {"X-Studio-Request": "1"}
    if credential_source == "bearer":
        supplied.update(headers(client))
    else:
        data["approval_token"] = client.app.state.settings.api_token
    response = client.post("/ui/approvals", data=data, headers=supplied)
    assert response.status_code == 200, response.text
    assert client.app.state.settings.api_token not in response.text
    assert_decision_actor(client, job["id"])
    with client.app.state.engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM production_jobs WHERE id=:id"), {"id": job["id"]},
        ).scalar_one() == "APPROVED"
        assert connection.execute(
            text("SELECT actor FROM audit_events WHERE action='TRANSITION' "
                 "AND subject_id=:id ORDER BY id DESC LIMIT 1"),
            {"id": job["id"]},
        ).scalar_one() == "local-api-user"


def test_invalid_bearer_cannot_fall_back_to_valid_form_token(client: TestClient) -> None:
    job = pending_job(client)
    before = counts(client)
    response = client.post(
        "/ui/approvals", data={"subject_id": job["id"], "decision": "APPROVED",
                               "approval_token": client.app.state.settings.api_token},
        headers={"X-Studio-Request": "1", "Authorization": "Bearer incorrect"},
    )
    assert response.status_code == 401
    assert counts(client) == before


def test_ui_displays_empty_password_field_not_server_token(client: TestClient) -> None:
    html = client.get("/workspace").text
    assert 'name="approval_token"' in html and 'type="password"' in html
    assert 'method="post" action="/ui/approvals"' in html  # No GET-token leakage if HTMX is unavailable.
    assert client.app.state.settings.api_token not in html


def test_valid_auth_preserves_invalid_job_state_rollback(client: TestClient) -> None:
    job = pending_job(client, pending=False)
    before = counts(client)
    request = {**payload(), "subject_kind": "JOB", "subject_id": job["id"]}
    response = client.post("/api/approvals", json=request, headers=headers(client))
    assert response.status_code == 409
    assert counts(client) == before


def test_approval_and_job_updates_rollback_if_decision_audit_fails(client: TestClient, monkeypatch) -> None:
    job = pending_job(client)
    before = counts(client)
    original = StudioService._audit

    def fail_decision(connection, actor, action, subject_kind, subject_id, old, new):
        if action == "DECIDE":
            raise DomainError("injected decision audit failure", 409)
        return original(connection, actor, action, subject_kind, subject_id, old, new)

    monkeypatch.setattr(StudioService, "_audit", staticmethod(fail_decision))
    request = {**payload(), "subject_kind": "JOB", "subject_id": job["id"]}
    response = client.post("/api/approvals", json=request, headers=headers(client))
    assert response.status_code == 409
    assert counts(client) == before
    with client.app.state.engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM production_jobs WHERE id=:id"), {"id": job["id"]},
        ).scalar_one() == "PENDING_APPROVAL"
