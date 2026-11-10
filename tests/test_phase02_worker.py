from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from studio_manager.config import PROJECT_ROOT
from studio_manager.service import StudioService
from studio_manager.worker import Worker

HEADERS = {"X-Studio-Request": "1"}


def make_project(client: TestClient, name: str = "Worker Lab") -> dict[str, object]:
    response = client.post("/api/catalog/projects", json={"name": name}, headers=HEADERS)
    assert response.status_code == 201, response.text
    return response.json()


def make_job(
    client: TestClient,
    project_id: str,
    job_type: str = "FOUNDATION_REVIEW",
    workspace_dir: str = "worker-test",
) -> dict[str, object]:
    response = client.post(
        "/api/jobs",
        json={
            "project_id": project_id,
            "job_type": job_type,
            "workspace_path": str(PROJECT_ROOT / "storage" / "20_TEMP" / workspace_dir),
            "requested_by": "creative-director",
            "target_application": "NONE",
        },
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    return response.json()


def queue(client: TestClient, job_id: str) -> None:
    response = client.post(
        f"/api/jobs/{job_id}/transitions",
        json={"target_status": "QUEUED", "actor": "creative-director", "payload": {}},
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text


def job_row(client: TestClient, job_id: str) -> dict[str, object]:
    rows = client.get("/api/studio").json()["production_jobs"]
    return next(row for row in rows if row["id"] == job_id)


def test_worker_processes_a_queued_job_end_to_end(client: TestClient) -> None:
    project = make_project(client)
    job = make_job(client, str(project["id"]))
    queue(client, str(job["id"]))

    worker = Worker(client.app.state.engine)
    outcome = worker.run_once()
    assert outcome["claimed"] == job["id"]
    assert outcome["status"] == "PENDING_APPROVAL"

    row = job_row(client, str(job["id"]))
    assert row["status"] == "PENDING_APPROVAL"
    assert row["started_at"] is not None

    events = [event for event in client.get("/api/studio").json()["job_events"] if event["job_id"] == job["id"]]
    kinds = [event["event_type"] for event in sorted(events, key=lambda item: item["sequence"])]
    assert kinds[0] == "CREATED"
    assert "CLAIMED" in kinds
    assert "STATUS_VALIDATING" in kinds
    assert kinds[-1] == "STATUS_PENDING_APPROVAL"

    result_file = Path(str(job["workspace_path"])) / "noop-adapter-result.json"
    assert result_file.is_file()
    assert json.loads(result_file.read_text(encoding="utf-8"))["adapter"] == "noop"


def test_worker_is_idle_with_empty_queue(client: TestClient) -> None:
    worker = Worker(client.app.state.engine)
    assert worker.run_once() == {"claimed": None, "status": "IDLE"}


def test_unsupported_job_type_is_blocked_without_execution(client: TestClient) -> None:
    project = make_project(client, "Blocked Lab")
    job = make_job(client, str(project["id"]), job_type="UNKNOWN_AUTOMATION")
    queue(client, str(job["id"]))

    outcome = Worker(client.app.state.engine).run_once()
    assert outcome["status"] == "BLOCKED"
    row = job_row(client, str(job["id"]))
    assert row["status"] == "BLOCKED"
    assert row["error_code"] == "UNSUPPORTED_JOB_TYPE"


def test_adapter_failure_marks_job_failed(client: TestClient) -> None:
    project = make_project(client, "Failure Lab")
    workspace = PROJECT_ROOT / "storage" / "20_TEMP" / "worker-failure"
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if workspace.exists() and workspace.is_dir():
        for child in workspace.iterdir():
            child.unlink()
        workspace.rmdir()
    workspace.write_text("not a directory", encoding="utf-8")
    try:
        job = make_job(client, str(project["id"]), workspace_dir="worker-failure")
        queue(client, str(job["id"]))
        outcome = Worker(client.app.state.engine).run_once()
        assert outcome["status"] == "FAILED"
        row = job_row(client, str(job["id"]))
        assert row["status"] == "FAILED"
        assert row["error_code"] == "WORKSPACE_INVALID"
    finally:
        if workspace.exists() and workspace.is_file():
            workspace.unlink()


def test_child_environment_is_allow_listed(client: TestClient) -> None:
    env = Worker.child_environment(
        {"id": "job_x", "workspace_path": str(PROJECT_ROOT / "storage" / "20_TEMP" / "env")}
    )
    assert env["STUDIO_JOB_ID"] == "job_x"
    assert env["PYTHONPATH"].endswith("src")
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert all(key in {"STUDIO_JOB_ID", "STUDIO_WORKSPACE", "PYTHONPATH", "PYTHONIOENCODING",
                       "PYTHONDONTWRITEBYTECODE", "SYSTEMROOT", "PATH", "TEMP", "TMP"} for key in env)


def test_service_and_worker_share_state(client: TestClient) -> None:
    assert isinstance(client.app.state.service, StudioService)
    assert Worker(client.app.state.engine).service is not client.app.state.service
