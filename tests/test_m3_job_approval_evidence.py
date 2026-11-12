"""M3: privileged job states require the existing trusted approval evidence."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from studio_manager.config import PROJECT_ROOT
from studio_manager.contracts import JobTransition
from studio_manager.service import DomainError, StudioService


def headers(client):
    return {"Authorization": f"Bearer {client.app.state.settings.api_token}", "X-Studio-Request": "1"}


def job(client, pending=True):
    project = client.post("/api/v1/projects", headers=headers(client), json={"name": "M3 " + uuid4().hex})
    assert project.status_code == 201
    created = client.post("/api/v1/jobs", headers=headers(client), json={
        "project_id": project.json()["id"], "job_type": "M3_METADATA_ONLY", "requested_by": "fixture",
        "workspace_path": str(PROJECT_ROOT / "storage" / "20_TEMP" / "m3-unused-workspace"),
    })
    assert created.status_code == 201
    identifier = created.json()["id"]
    if pending:
        for state in ("QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL"):
            assert transition(client, identifier, state, "v1") == 200
    return identifier


def transition(client, identifier, state, via, **fields):
    if via == "direct":
        try:
            client.app.state.service.transition_job(
                identifier, JobTransition(target_status=state, actor="fixture", **fields),
            )
            return 200
        except DomainError as exc:
            return exc.status_code
    prefix = {"legacy": "/api/jobs/", "v1": "/api/v1/jobs/", "ui": "/ui/jobs/"}[via]
    url = prefix + identifier + "/transitions"
    if via == "ui":
        return client.post(url, headers=headers(client), data={"target_status": state}).status_code
    return client.post(
        url, headers=headers(client), json={"target_status": state, "actor": "fixture", **fields},
    ).status_code


def approve(client, identifier, decision="APPROVED"):
    response = client.post("/api/v1/approvals", headers=headers(client), json={
        "subject_kind": "JOB", "subject_id": identifier, "decision": decision, "decided_by": "forged-input",
    })
    assert response.status_code == 201, response.text
    return response.json()


def snapshot(client):
    with client.app.state.engine.connect() as connection:
        return {
            "jobs": [dict(r) for r in connection.execute(text("SELECT * FROM production_jobs ORDER BY id")).mappings()],
            "approvals": [dict(r) for r in connection.execute(text("SELECT * FROM approvals ORDER BY id")).mappings()],
            "events": [dict(r) for r in connection.execute(text("SELECT * FROM job_events ORDER BY id")).mappings()],
            "audits": [dict(r) for r in connection.execute(text("SELECT * FROM audit_events ORDER BY id")).mappings()],
        }


def state(client, identifier):
    with client.app.state.engine.connect() as connection:
        return connection.execute(
            text("SELECT status FROM production_jobs WHERE id=:id"), {"id": identifier},
        ).scalar_one()


def test_supported_api_sequence_cannot_approve_or_publish_without_evidence(client):
    identifier = job(client, pending=False)
    responses = []
    for target in ("QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL", "APPROVED", "PUBLISHED"):
        response = transition(client, identifier, target, "v1")
        responses.append({"target": target, "http": response, "state": state(client, identifier)})
    data = snapshot(client)
    print(json.dumps({"responses": responses, "approval_evidence": data["approvals"],
                      "job_events": data["events"], "audit_events": data["audits"]}))
    assert responses[4]["http"] == 409
    assert responses[5]["http"] == 409
    assert state(client, identifier) == "PENDING_APPROVAL"
    assert data["approvals"] == []
    assert [r["event_type"] for r in data["events"]] == [
        "CREATED", "STATUS_QUEUED", "STATUS_RUNNING", "STATUS_VALIDATING", "STATUS_PENDING_APPROVAL",
    ]


@pytest.mark.parametrize("via", ["legacy", "v1", "ui", "direct"])
def test_generic_approved_is_not_an_approval_workflow(client, via):
    identifier = job(client)
    before = snapshot(client)
    assert transition(client, identifier, "APPROVED", via, payload={"decision": "APPROVED"}) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("via", ["legacy", "v1", "ui", "direct"])
def test_forged_approved_state_without_evidence_cannot_publish(client, via):
    identifier = job(client)
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE production_jobs SET status='APPROVED' WHERE id=:id"), {"id": identifier})
    before = snapshot(client)
    assert transition(client, identifier, "PUBLISHED", via) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("via", ["legacy", "v1", "ui", "direct"])
def test_valid_trusted_approval_preserves_publish_lifecycle(client, via):
    identifier = job(client)
    evidence = approve(client, identifier)
    assert evidence["decided_by"] == "local-api-user"
    assert state(client, identifier) == "APPROVED"
    assert transition(client, identifier, "PUBLISHED", via) == 200
    assert state(client, identifier) == "PUBLISHED"
    data = snapshot(client)
    event = next(r for r in data["events"] if r["event_type"] == "STATUS_PUBLISHED")
    assert json.loads(event["payload_json"])["approval_id"] == evidence["id"]
    for audit in data["audits"]:
        after = json.loads(audit["after_json"] or "{}")
        if audit["action"] == "TRANSITION" and after.get("status") in {"APPROVED", "PUBLISHED"}:
            assert after["approval_id"] == evidence["id"]
    before = snapshot(client)
    assert transition(client, identifier, "PUBLISHED", via) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("decision", ["REJECTED", "CHANGES_REQUESTED"])
def test_negative_decision_cannot_authorize_privileged_states(client, decision):
    identifier = job(client)
    evidence = approve(client, identifier, decision)
    assert state(client, identifier) == "BLOCKED"
    before = snapshot(client)
    assert transition(client, identifier, "APPROVED", "direct", approval_id=evidence["id"]) == 409
    assert transition(client, identifier, "PUBLISHED", "v1", approval_id=evidence["id"]) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("via", ["legacy", "v1", "direct"])
def test_explicit_unrelated_approval_id_is_rejected(client, via):
    first, second = job(client), job(client)
    approve(client, first)
    wrong = approve(client, second)
    before = snapshot(client)
    assert transition(client, first, "PUBLISHED", via, approval_id=wrong["id"]) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("problem", [
    "missing_audit", "rejected_row", "wrong_subject", "invalid_audit", "audit_actor_mismatch", "audit_row_mismatch",
])
def test_invalid_evidence_rows_cannot_authorize_publish(client, problem):
    identifier = job(client)
    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE production_jobs SET status='APPROVED' WHERE id=:id"), {"id": identifier})
        connection.execute(text(
            "INSERT INTO approvals(id,subject_kind,subject_id,decision,decided_by,created_at) "
            "VALUES('invalid',:kind,:job,:decision,'local-api-user','2026-11-11T00:00:00+00:00')"
        ), {"job": identifier, "kind": "MCP_OPERATION" if problem == "wrong_subject" else "JOB",
            "decision": "REJECTED" if problem == "rejected_row" else "APPROVED"})
        if problem in {"invalid_audit", "audit_actor_mismatch", "audit_row_mismatch"}:
            row = dict(connection.execute(text("SELECT * FROM approvals WHERE id='invalid'")).mappings().one())
            if problem == "audit_row_mismatch":
                row["id"] = "other"
            connection.execute(text(
                "INSERT INTO audit_events(actor,action,subject_kind,subject_id,after_json,created_at) "
                "VALUES(:actor,'DECIDE','JOB',:job,:after,'now')"
            ), {"job": identifier, "actor": "other" if problem == "audit_actor_mismatch" else "local-api-user",
                "after": "not json" if problem == "invalid_audit" else json.dumps(row)})
    before = snapshot(client)
    assert transition(client, identifier, "PUBLISHED", "direct") == 409
    assert snapshot(client) == before


def test_unauthenticated_v1_transition_with_valid_evidence_is_rejected(client):
    identifier = job(client)
    approve(client, identifier)
    before = snapshot(client)
    response = client.post(
        f"/api/v1/jobs/{identifier}/transitions", headers={"X-Studio-Request": "1"},
        json={"target_status": "PUBLISHED", "actor": "forged"},
    )
    assert response.status_code == 401
    assert snapshot(client) == before


def test_unauthenticated_legacy_request_cannot_manufacture_approval(client):
    identifier = job(client)
    before = snapshot(client)
    response = client.post(
        f"/api/jobs/{identifier}/transitions", headers={"X-Studio-Request": "1"},
        json={"target_status": "APPROVED", "actor": "creative-director", "payload": {"decision": "APPROVED"}},
    )
    assert response.status_code == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("operation", ["approval", "publish"])
def test_privileged_transition_audit_failure_rolls_back_everything(client, monkeypatch, operation):
    identifier = job(client)
    if operation == "publish":
        approve(client, identifier)
    before = snapshot(client)
    original = StudioService._audit

    def fail_transition(connection, actor, action, kind, subject_id, old, new):
        if action == "TRANSITION" and new and new["status"] in {"APPROVED", "PUBLISHED"}:
            raise DomainError("injected transition audit failure", 409)
        return original(connection, actor, action, kind, subject_id, old, new)

    monkeypatch.setattr(StudioService, "_audit", staticmethod(fail_transition))
    if operation == "approval":
        response = client.post("/api/v1/approvals", headers=headers(client), json={
            "subject_kind": "JOB", "subject_id": identifier, "decision": "APPROVED", "decided_by": "fixture",
        })
        assert response.status_code == 409
    else:
        assert transition(client, identifier, "PUBLISHED", "v1") == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("target", ["APPROVED", "PUBLISHED"])
def test_private_transition_helper_cannot_skip_evidence(client, target):
    identifier = job(client)
    if target == "PUBLISHED":
        with client.app.state.engine.begin() as connection:
            connection.execute(text("UPDATE production_jobs SET status='APPROVED' WHERE id=:id"), {"id": identifier})
    before = snapshot(client)
    with pytest.raises(DomainError, match="approval|APPROVED"):
        with client.app.state.engine.begin() as connection:
            client.app.state.service._transition_job(
                connection, identifier, JobTransition(target_status=target, actor="fixture"),
            )
    assert snapshot(client) == before


def test_repeat_approval_workflow_is_rejected_without_new_records(client):
    identifier = job(client)
    approve(client, identifier)
    before = snapshot(client)
    response = client.post("/api/v1/approvals", headers=headers(client), json={
        "subject_kind": "JOB", "subject_id": identifier, "decision": "APPROVED", "decided_by": "fixture",
    })
    assert response.status_code == 409
    assert snapshot(client) == before


def test_latest_negative_decision_cannot_reuse_earlier_approval(client):
    identifier = job(client)
    original = approve(client, identifier)
    with client.app.state.engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO approvals(id,subject_kind,subject_id,decision,decided_by,created_at) "
            "VALUES('newer_rejection','JOB',:id,'REJECTED','local-api-user','now')"
        ), {"id": identifier})
    before = snapshot(client)
    assert transition(client, identifier, "PUBLISHED", "v1", approval_id=original["id"]) == 409
    assert snapshot(client) == before


@pytest.mark.parametrize("explicit_correct_reference", [False, True])
def test_conflicting_nested_approval_reference_is_not_ignored(client, explicit_correct_reference):
    identifier, other = job(client), job(client)
    correct, unrelated = approve(client, identifier), approve(client, other)
    fields = {"payload": {"approval_id": unrelated["id"]}}
    if explicit_correct_reference:
        fields["approval_id"] = correct["id"]
    before = snapshot(client)
    assert transition(client, identifier, "PUBLISHED", "v1", **fields) == 409
    assert snapshot(client) == before
