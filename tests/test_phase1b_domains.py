from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from studio_manager.config import PROJECT_ROOT

HEADERS = {"X-Studio-Request": "1"}


def create_project(client: TestClient, name: str = "Lantern District") -> dict[str, object]:
    response = client.post("/api/catalog/projects", json={"name": name}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


def create_job(client: TestClient, project_id: str) -> dict[str, object]:
    workspace = PROJECT_ROOT / "storage" / "10_DEVELOPMENT" / "jobs" / "test-job"
    response = client.post(
        "/api/jobs",
        json={
            "project_id": project_id,
            "job_type": "SHOT_REVIEW",
            "workspace_path": str(workspace),
            "requested_by": "creative-director",
            "target_application": "NONE",
        },
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    return response.json()


def transition(client: TestClient, job_id: str, target: str):
    return client.post(
        f"/api/jobs/{job_id}/transitions",
        json={"target_status": target, "actor": "creative-director", "payload": {}},
        headers=HEADERS,
    )


def test_state_changes_require_studio_header(client: TestClient) -> None:
    response = client.post("/api/catalog/projects", json={"name": "Blocked Request"})
    assert response.status_code == 403
    assert response.json() == {"error": "missing Studio request header"}


def test_complete_catalog_hierarchy_and_duplicate_protection(client: TestClient) -> None:
    project = create_project(client)
    duplicate = client.post("/api/catalog/projects", json={"name": project["name"]}, headers=HEADERS)
    assert duplicate.status_code == 409

    series = client.post(
        "/api/catalog/series",
        json={"project_id": project["id"], "name": "The Copper Kite"},
        headers=HEADERS,
    )
    assert series.status_code == 201
    episode = client.post(
        "/api/catalog/episodes",
        json={"series_id": series.json()["id"], "code": "E01", "title": "First Flight"},
        headers=HEADERS,
    )
    assert episode.status_code == 201
    scene = client.post(
        "/api/catalog/scenes",
        json={"episode_id": episode.json()["id"], "code": "S010", "title": "Workshop"},
        headers=HEADERS,
    )
    assert scene.status_code == 201
    shot = client.post(
        "/api/catalog/shots",
        json={"scene_id": scene.json()["id"], "code": "SH010", "frame_start": 1, "frame_end": 96, "fps": 24},
        headers=HEADERS,
    )
    assert shot.status_code == 201
    character = client.post(
        "/api/characters",
        json={"project_id": project["id"], "code": "HERO", "name": "Nuri"},
        headers=HEADERS,
    )
    assert character.status_code == 201

    snapshot = client.get("/api/studio").json()
    assert len(snapshot["projects"]) == 1
    assert len(snapshot["series"]) == 1
    assert len(snapshot["episodes"]) == 1
    assert len(snapshot["scenes"]) == 1
    assert len(snapshot["shots"]) == 1
    assert len(snapshot["characters"]) == 1


def test_asset_versions_accept_only_managed_workspaces(client: TestClient) -> None:
    project = create_project(client)
    asset_response = client.post(
        "/api/assets",
        json={
            "project_id": project["id"],
            "code": "PROP_KITE",
            "name": "Copper Kite",
            "asset_type": "PROP",
        },
        headers=HEADERS,
    )
    assert asset_response.status_code == 201
    asset_id = asset_response.json()["id"]
    workspace = PROJECT_ROOT / "storage" / "10_DEVELOPMENT" / "assets" / asset_id
    version = client.post(
        f"/api/assets/{asset_id}/versions",
        json={"workspace_path": str(workspace)},
        headers=HEADERS,
    )
    assert version.status_code == 201
    assert version.json()["version"] == 1

    protected = client.post(
        f"/api/assets/{asset_id}/versions",
        json={"workspace_path": r"D:\Projects\01_3D_Blender\Blender Project"},
        headers=HEADERS,
    )
    assert protected.status_code == 400
    assert "managed development" in protected.json()["error"]


def test_job_transitions_are_atomic_and_approval_gated(client: TestClient) -> None:
    project = create_project(client)
    job = create_job(client, str(project["id"]))

    invalid = transition(client, str(job["id"]), "RUNNING")
    assert invalid.status_code == 409
    snapshot = client.get("/api/studio").json()
    assert snapshot["production_jobs"][0]["status"] == "DRAFT"
    assert [event["sequence"] for event in snapshot["job_events"]] == [1]

    for target in ("QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL"):
        response = transition(client, str(job["id"]), target)
        assert response.status_code == 200, response.text

    approval = client.post(
        "/api/approvals",
        json={
            "subject_kind": "JOB",
            "subject_id": job["id"],
            "decision": "APPROVED",
            "decided_by": "creative-director",
            "notes": "Foundation evidence accepted.",
        },
        headers={**HEADERS, "Authorization": f"Bearer {client.app.state.settings.api_token}"},
    )
    assert approval.status_code == 201
    published = transition(client, str(job["id"]), "PUBLISHED")
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"

    snapshot = client.get("/api/studio").json()
    sequences = sorted(event["sequence"] for event in snapshot["job_events"])
    assert sequences == list(range(1, 8))
    assert snapshot["approvals"][0]["decision"] == "APPROVED"


def test_evidence_tables_are_append_only(client: TestClient) -> None:
    project = create_project(client)
    job = create_job(client, str(project["id"]))
    engine = client.app.state.engine
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE job_events SET event_type='ALTERED' WHERE job_id=:id"), {"id": job["id"]})
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_events"))
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO approvals(id,subject_kind,subject_id,decision,decided_by,created_at) "
                "VALUES('apr_trigger','JOB',:id,'REJECTED','test','2026-10-30T00:00:00+00:00')"
            ),
            {"id": job["id"]},
        )
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE approvals SET notes='altered' WHERE id='apr_trigger'"))


def test_htmx_is_local_and_matches_manifest(client: TestClient) -> None:
    response = client.get("/workspace")
    assert response.status_code == 200
    assert "/static/vendor/htmx-2.0.11.min.js" in response.text
    assert "cdn." not in response.text
    manifest_path = PROJECT_ROOT / "src" / "studio_manager" / "static" / "vendor" / "htmx.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    vendor = manifest_path.parent / "htmx-2.0.11.min.js"
    assert vendor.stat().st_size == manifest["bytes"] == 52182
    assert hashlib.sha256(vendor.read_bytes()).hexdigest() == manifest["sha256"]


def test_htmx_project_form_returns_updated_partial(client: TestClient) -> None:
    response = client.post(
        "/ui/projects",
        data={"name": "HTMX Registry"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert "HTMX Registry" in response.text
    assert "<!doctype html>" not in response.text

def test_template_patterns_are_v_mode_safe(client: TestClient) -> None:
    html = client.get("/workspace").text
    assert "pattern=\"[A-Za-z0-9_-]+\"" not in html
    assert html.count("pattern=\"[A-Za-z0-9_\\-]+\"") == 2
