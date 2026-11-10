from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from studio_manager.auth import require_api_token
from studio_manager.backup_service import BackupService
from studio_manager.contracts import (
    ApprovalCreate,
    AssetCreate,
    AssetUpdate,
    AssetVersionCreate,
    AssetVersionTransition,
    CharacterCreate,
    CharacterUpdate,
    CharacterVariantCreate,
    CharacterVariantUpdate,
    ImportRequest,
    JobCreate,
    JobTransition,
    ProjectCreate,
    ProjectUpdate,
)
from studio_manager.import_service import Phase02ImportService
from studio_manager.phase03a_service import Phase03AService

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_token)])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def phase03a(request: Request) -> Phase03AService:
    return request.app.state.phase03a


def importer(request: Request) -> Phase02ImportService:
    return request.app.state.phase03a_importer


def backups(request: Request) -> BackupService:
    return request.app.state.phase03a_backups


ServiceDep = Annotated[Phase03AService, Depends(phase03a)]
ImportDep = Annotated[Phase02ImportService, Depends(importer)]
BackupDep = Annotated[BackupService, Depends(backups)]


@router.get("/projects")
def list_projects(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    status_value: Annotated[str | None, Query(alias="status")] = None,
):
    return service.list_records("projects", limit=limit, offset=offset, filters={"status": status_value})


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, service: ServiceDep):
    return service.legacy.create_project(payload, actor="local-api-user")


@router.get("/projects/{item_id}")
def get_project(item_id: str, service: ServiceDep):
    return service.get_record("projects", item_id)


@router.patch("/projects/{item_id}")
def update_project(item_id: str, payload: ProjectUpdate, service: ServiceDep):
    return service.update_record("projects", item_id, payload.model_dump(exclude_unset=True), "local-api-user")


@router.delete("/projects/{item_id}")
def delete_project(item_id: str, service: ServiceDep):
    return service.delete_record("projects", item_id, "local-api-user")


@router.get("/assets")
def list_assets(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    project_id: str | None = None,
    asset_type: str | None = None,
    lifecycle_state: str | None = None,
):
    return service.list_records(
        "assets",
        limit=limit,
        offset=offset,
        filters={"project_id": project_id, "asset_type": asset_type, "lifecycle_state": lifecycle_state},
    )


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, service: ServiceDep):
    return service.legacy.create_asset(payload, actor="local-api-user")


@router.get("/assets/{item_id}")
def get_asset(item_id: str, service: ServiceDep):
    return service.get_record("assets", item_id)


@router.patch("/assets/{item_id}")
def update_asset(item_id: str, payload: AssetUpdate, service: ServiceDep):
    return service.update_record("assets", item_id, payload.model_dump(exclude_unset=True), "local-api-user")


@router.delete("/assets/{item_id}")
def delete_asset(item_id: str, service: ServiceDep):
    return service.delete_record("assets", item_id, "local-api-user")


@router.get("/assets/{asset_id}/versions")
def list_asset_versions(asset_id: str, service: ServiceDep, limit: Limit = 50, offset: Offset = 0):
    return service.list_records("asset_versions", limit=limit, offset=offset, filters={"asset_id": asset_id})


@router.post("/assets/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
def create_asset_version(asset_id: str, payload: AssetVersionCreate, service: ServiceDep):
    return service.legacy.create_asset_version(asset_id, payload, actor="local-api-user")


@router.post("/asset-versions/{item_id}/transitions")
def transition_asset_version(item_id: str, payload: AssetVersionTransition, service: ServiceDep):
    return service.legacy.transition_asset_version(item_id, payload, actor="local-api-user")


@router.get("/characters")
def list_characters(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    project_id: str | None = None,
    bible_status: str | None = None,
):
    return service.list_records(
        "characters", limit=limit, offset=offset, filters={"project_id": project_id, "bible_status": bible_status}
    )


@router.post("/characters", status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate, service: ServiceDep):
    return service.legacy.create_character(payload, actor="local-api-user")


@router.get("/characters/{item_id}")
def get_character(item_id: str, service: ServiceDep):
    return service.get_record("characters", item_id)


@router.patch("/characters/{item_id}")
def update_character(item_id: str, payload: CharacterUpdate, service: ServiceDep):
    return service.update_record("characters", item_id, payload.model_dump(exclude_unset=True), "local-api-user")


@router.delete("/characters/{item_id}")
def delete_character(item_id: str, service: ServiceDep):
    return service.delete_record("characters", item_id, "local-api-user")


@router.get("/characters/{character_id}/variants")
def list_character_variants(character_id: str, service: ServiceDep, limit: Limit = 50, offset: Offset = 0):
    return service.list_records(
        "character_variants", limit=limit, offset=offset, filters={"character_id": character_id}
    )


@router.post("/characters/{character_id}/variants", status_code=status.HTTP_201_CREATED)
def create_character_variant(character_id: str, payload: CharacterVariantCreate, service: ServiceDep):
    return service.create_character_variant(character_id, payload.model_dump(), "local-api-user")


@router.patch("/character-variants/{item_id}")
def update_character_variant(item_id: str, payload: CharacterVariantUpdate, service: ServiceDep):
    changes = payload.model_dump(exclude_unset=True)
    if "config" in changes:
        import json

        changes["config_json"] = json.dumps(changes.pop("config"), sort_keys=True)
    return service.update_record("character_variants", item_id, changes, "local-api-user")


@router.delete("/character-variants/{item_id}")
def delete_character_variant(item_id: str, service: ServiceDep):
    return service.delete_record("character_variants", item_id, "local-api-user")


@router.get("/jobs")
def list_jobs(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    project_id: str | None = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
    job_type: str | None = None,
):
    return service.list_records(
        "production_jobs",
        limit=limit,
        offset=offset,
        filters={"project_id": project_id, "status": status_value, "job_type": job_type},
    )


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, service: ServiceDep):
    return service.legacy.create_job(payload.model_copy(update={"requested_by": "local-api-user"}))


@router.get("/jobs/{item_id}")
def get_job(item_id: str, service: ServiceDep):
    return service.get_record("production_jobs", item_id)


@router.post("/jobs/{item_id}/transitions")
def transition_job(item_id: str, payload: JobTransition, service: ServiceDep):
    return service.legacy.transition_job(item_id, payload.model_copy(update={"actor": "local-api-user"}))


@router.get("/approvals")
def list_approvals(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    decision: str | None = None,
):
    return service.list_records(
        "approvals",
        limit=limit,
        offset=offset,
        filters={"subject_kind": subject_kind, "subject_id": subject_id, "decision": decision},
    )


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
def create_approval(payload: ApprovalCreate, service: ServiceDep):
    return service.legacy.create_approval(payload.model_copy(update={"decided_by": "local-api-user"}))


@router.get("/approvals/{item_id}")
def get_approval(item_id: str, service: ServiceDep):
    return service.get_record("approvals", item_id)


@router.get("/audit-events")
def list_audit_events(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    subject_kind: str | None = None,
    subject_id: str | None = None,
    action: str | None = None,
):
    return service.list_records(
        "audit_events",
        limit=limit,
        offset=offset,
        filters={"subject_kind": subject_kind, "subject_id": subject_id, "action": action},
    )


@router.get("/audit-events/{item_id}")
def get_audit_event(item_id: str, service: ServiceDep):
    return service.get_record("audit_events", item_id)


@router.post("/imports", status_code=status.HTTP_201_CREATED)
def run_import(payload: ImportRequest, import_service: ImportDep):
    return import_service.run(
        payload.source_kind,
        payload.source_path,
        dry_run=payload.dry_run,
        actor="local-api-user",
    )


@router.get("/imports")
def list_imports(
    service: ServiceDep,
    limit: Limit = 50,
    offset: Offset = 0,
    source_kind: str | None = None,
    status_value: Annotated[str | None, Query(alias="status")] = None,
):
    return service.list_records(
        "import_batches", limit=limit, offset=offset, filters={"source_kind": source_kind, "status": status_value}
    )


@router.post("/backups", status_code=status.HTTP_201_CREATED)
def create_backup(backup_service: BackupDep):
    return backup_service.create()


@router.get("/backups")
def list_backups(service: ServiceDep, limit: Limit = 50, offset: Offset = 0):
    return service.list_records("backups", limit=limit, offset=offset, filters={})
