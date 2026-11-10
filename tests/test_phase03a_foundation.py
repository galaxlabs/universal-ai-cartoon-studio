from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from studio_manager.config import PROJECT_ROOT
from studio_manager.models import Base
from studio_manager.service import DomainError
from studio_manager.storage_service import LocalStorageService


def auth_headers(client: TestClient) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {client.app.state.settings.api_token}",
        "X-Studio-Request": "1",
    }


def create_v1_project(client: TestClient, name: str = "Phase 03 Atlas") -> dict[str, object]:
    response = client.post("/api/v1/projects", json={"name": name}, headers=auth_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_required_sqlalchemy_models_are_registered() -> None:
    assert {
        "projects",
        "series",
        "episodes",
        "scenes",
        "shots",
        "characters",
        "character_variants",
        "assets",
        "asset_versions",
        "production_jobs",
        "approvals",
        "audit_events",
        "import_batches",
        "backups",
        "users",
        "app_settings",
    } <= set(Base.metadata.tables)


def test_v1_requires_bearer_token_and_studio_write_header(client: TestClient) -> None:
    missing_token = client.post("/api/v1/projects", json={"name": "No Token"}, headers={"X-Studio-Request": "1"})
    assert missing_token.status_code == 401

    token_only = client.post(
        "/api/v1/projects",
        json={"name": "No Intent Header"},
        headers={"Authorization": f"Bearer {client.app.state.settings.api_token}"},
    )
    assert token_only.status_code == 403

    invalid = client.get("/api/v1/projects", headers={"Authorization": "Bearer invalid-token-value-000000000"})
    assert invalid.status_code == 401


def test_v1_crud_filtering_pagination_and_no_cascade(client: TestClient) -> None:
    headers = auth_headers(client)
    first = create_v1_project(client, "Atlas A")
    second = create_v1_project(client, "Atlas B")

    page = client.get("/api/v1/projects?status=DRAFT&limit=1&offset=1", headers=headers)
    assert page.status_code == 200
    assert page.json()["count"] == 2
    assert len(page.json()["items"]) == 1

    updated = client.patch(
        f"/api/v1/projects/{first['id']}",
        json={"status": "ACTIVE"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "ACTIVE"

    asset = client.post(
        "/api/v1/assets",
        json={"project_id": first["id"], "code": "PROP_01", "name": "Lantern", "asset_type": "PROP"},
        headers=headers,
    )
    assert asset.status_code == 201
    filtered = client.get(f"/api/v1/assets?project_id={first['id']}&asset_type=PROP", headers=headers)
    assert filtered.json()["count"] == 1

    blocked_project_delete = client.delete(f"/api/v1/projects/{first['id']}", headers=headers)
    assert blocked_project_delete.status_code == 409
    deleted = client.delete(f"/api/v1/projects/{second['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_character_variants_jobs_approvals_and_audit_api(client: TestClient) -> None:
    headers = auth_headers(client)
    project = create_v1_project(client)
    character = client.post(
        "/api/v1/characters",
        json={"project_id": project["id"], "code": "HERO", "name": "Nuri"},
        headers=headers,
    ).json()
    variant = client.post(
        f"/api/v1/characters/{character['id']}/variants",
        json={"code": "WINTER", "name": "Winter Costume", "config": {"coat": "blue"}},
        headers=headers,
    )
    assert variant.status_code == 201
    assert client.get(f"/api/v1/characters/{character['id']}/variants", headers=headers).json()["count"] == 1

    workspace = PROJECT_ROOT / "storage" / "10_DEVELOPMENT" / "jobs" / "phase03a-test"
    job = client.post(
        "/api/v1/jobs",
        json={
            "project_id": project["id"],
            "job_type": "METADATA_ONLY",
            "workspace_path": str(workspace),
            "requested_by": "forged-actor",
            "target_application": "NONE",
        },
        headers=headers,
    )
    assert job.status_code == 201
    assert job.json()["status"] == "DRAFT"
    assert job.json()["requested_by"] == "local-api-user"
    assert client.get(f"/api/v1/jobs?project_id={project['id']}", headers=headers).json()["count"] == 1

    approval = client.post(
        "/api/v1/approvals",
        json={
            "subject_kind": "MCP_OPERATION",
            "subject_id": "phase03a_review",
            "decision": "APPROVED",
            "decided_by": "forged-director",
        },
        headers=headers,
    )
    assert approval.status_code == 201
    assert approval.json()["decided_by"] == "local-api-user"
    assert client.get("/api/v1/approvals?subject_kind=MCP_OPERATION", headers=headers).json()["count"] == 1
    assert client.get("/api/v1/audit-events?action=CREATE", headers=headers).json()["count"] >= 3


def test_approved_asset_versions_and_evidence_are_immutable(client: TestClient) -> None:
    headers = auth_headers(client)
    project = create_v1_project(client)
    asset = client.post(
        "/api/v1/assets",
        json={"project_id": project["id"], "code": "MODEL_01", "name": "Model", "asset_type": "PROP"},
        headers=headers,
    ).json()
    workspace = PROJECT_ROOT / "storage" / "20_TEMP" / "pytest" / "approved-version"
    workspace.mkdir(parents=True, exist_ok=True)
    direct_approved = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        json={"workspace_path": str(workspace), "status": "APPROVED"},
        headers=headers,
    )
    assert direct_approved.status_code == 422
    version_response = client.post(
        f"/api/v1/assets/{asset['id']}/versions",
        json={"workspace_path": str(workspace), "sha256": "a" * 64},
        headers=headers,
    )
    assert version_response.status_code == 201
    version = version_response.json()
    for target in ("VALIDATING", "PENDING_APPROVAL"):
        transition = client.post(
            f"/api/v1/asset-versions/{version['id']}/transitions",
            json={"target_status": target},
            headers=headers,
        )
        assert transition.status_code == 200, transition.text
    approval = client.post(
        "/api/v1/approvals",
        json={
            "subject_kind": "ASSET_VERSION",
            "subject_id": version["id"],
            "decision": "APPROVED",
            "decided_by": "forged-director",
        },
        headers=headers,
    )
    assert approval.status_code == 201, approval.text
    engine = client.app.state.engine
    with pytest.raises(DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE asset_versions SET status='DRAFT' WHERE id=:id"), {"id": version["id"]})
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_events"))


def test_secure_storage_is_atomic_hashed_and_confined(tmp_path: Path) -> None:
    storage = LocalStorageService(tmp_path / "managed")
    stored = storage.write_bytes("assets/example.bin", b"phase03a")
    assert stored.sha256 == hashlib.sha256(b"phase03a").hexdigest()
    assert storage.read_bytes("assets/example.bin") == b"phase03a"
    assert not list((tmp_path / "managed" / "assets").glob("*.tmp"))

    with pytest.raises(DomainError, match="already exists"):
        storage.write_bytes("assets/example.bin", b"replacement")
    with pytest.raises(DomainError, match="safe relative"):
        storage.write_bytes("../escape.bin", b"blocked")
    with pytest.raises(DomainError, match="safe relative"):
        storage.write_bytes(str((tmp_path / "absolute.bin").resolve()), b"blocked")

    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "linked-root"
    try:
        linked_root.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable for this Windows account")
    with pytest.raises(DomainError, match="root must not be a symlink"):
        LocalStorageService(linked_root)
    link = tmp_path / "managed" / "linked"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(DomainError, match="symlink"):
        storage.write_bytes("linked/escape.bin", b"blocked")


def test_phase02_import_is_dry_runnable_idempotent_and_conflict_aware(client: TestClient) -> None:
    headers = auth_headers(client)
    source = PROJECT_ROOT / "config" / "phase02.skills.json"
    payload = {"source_kind": "PHASE02_SKILLS", "source_path": str(source), "dry_run": True}
    dry_run = client.post("/api/v1/imports", json=payload, headers=headers)
    assert dry_run.status_code == 201, dry_run.text
    assert dry_run.json()["status"] == "DRY_RUN"
    assert dry_run.json()["counts"]["created"] == 14
    assert Path(dry_run.json()["unknown_fields_path"]).is_file()

    payload["dry_run"] = False
    imported = client.post("/api/v1/imports", json=payload, headers=headers)
    assert imported.status_code == 201, imported.text
    assert imported.json()["counts"]["created"] == 14
    repeated = client.post("/api/v1/imports", json=payload, headers=headers)
    assert repeated.status_code == 201
    assert repeated.json()["counts"]["skipped"] == 14

    with client.app.state.engine.begin() as connection:
        connection.execute(text("UPDATE skills SET name='manual-change' WHERE id='BLENDER_CORE'"))
    conflict = client.post("/api/v1/imports", json=payload, headers=headers)
    assert conflict.status_code == 409
    batches = client.get("/api/v1/imports?status=CONFLICT", headers=headers).json()
    assert batches["count"] == 1


def test_phase02_report_import_and_database_backup_recovery(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import studio_manager.import_service as import_module

    headers = auth_headers(client)
    # Public checkouts must not require production reports, logs or private data.
    monkeypatch.setattr(import_module, "PROJECT_ROOT", tmp_path)
    report = tmp_path / "storage" / "80_REPORTS" / "phase02_validation.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps({"phase": "PHASE_02_TEST_FIXTURE", "status": "PASS", "generated_at": "2026-11-10T00:00:00Z"}),
        encoding="utf-8",
    )
    payload = {"source_kind": "PHASE02_REPORT", "source_path": str(report), "dry_run": False}
    imported = client.post("/api/v1/imports", json=payload, headers=headers)
    assert imported.status_code == 201, imported.text
    repeated = client.post("/api/v1/imports", json=payload, headers=headers)
    assert repeated.json()["counts"]["skipped"] == 1

    backup = client.post("/api/v1/backups", headers=headers)
    assert backup.status_code == 201, backup.text
    details = backup.json()
    assert details["integrity_check"] == "ok"
    assert details["migration_revision"] == "0005_agent_skills_registry"
    assert details["restore_open_test"] is True
    backup_path = Path(details["path"])
    assert backup_path.is_file()

    recovery = client.app.state.settings.project_root / "storage" / "20_TEMP" / "recovery" / "restored.db"
    restored = client.app.state.phase03a_backups.restore_copy(backup_path, recovery)
    assert restored["integrity_check"] == "ok"
    connection = sqlite3.connect(restored["destination"])
    try:
        assert connection.execute("SELECT COUNT(*) FROM validation_reports").fetchone()[0] == 1
    finally:
        connection.close()
    backup_path.write_bytes(backup_path.read_bytes() + b"tampered")
    with pytest.raises(DomainError, match="SHA-256"):
        client.app.state.phase03a_backups.restore_copy(
            backup_path,
            recovery.with_name("tampered-restore.db"),
        )
