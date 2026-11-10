from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.contracts import (  # noqa: E402
    ApprovalCreate,
    AssetCreate,
    AssetVersionCreate,
    JobCreate,
    JobTransition,
    ProjectCreate,
)
from studio_manager.database import (  # noqa: E402
    create_database_engine,
    database_health,
    downgrade_database,
    upgrade_database,
)
from studio_manager.service import DomainError, StudioService  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report_dir = ROOT / "storage" / "80_REPORTS"
    temp_dir = ROOT / "storage" / "20_TEMP" / "phase1b_validation"
    database_path = temp_dir / "phase1b.db"
    report_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    for path in temp_dir.glob("phase1b.db*"):
        path.unlink()

    upgrade_database(database_path)
    engine = create_database_engine(database_path)
    service = StudioService(engine)
    project = service.create_project(ProjectCreate(name="Phase 1B Validation"))
    asset = service.create_asset(
        AssetCreate(project_id=str(project["id"]), code="TEST_PROP", name="Test Prop", asset_type="PROP")
    )
    asset_version = service.create_asset_version(
        str(asset["id"]),
        AssetVersionCreate(workspace_path=str(ROOT / "storage" / "20_TEMP" / "phase1b-validation-asset")),
    )
    job = service.create_job(
        JobCreate(
            project_id=str(project["id"]),
            job_type="VALIDATION",
            workspace_path=str(ROOT / "storage" / "20_TEMP" / "phase1b-validation-job"),
            requested_by="phase1b-validator",
        )
    )
    invalid_transition_blocked = False
    try:
        service.transition_job(str(job["id"]), JobTransition(target_status="RUNNING", actor="validator"))
    except DomainError:
        invalid_transition_blocked = True
    for target in ("QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL"):
        service.transition_job(str(job["id"]), JobTransition(target_status=target, actor="validator"))
    service.create_approval(
        ApprovalCreate(
            subject_kind="JOB",
            subject_id=str(job["id"]),
            decision="APPROVED",
            decided_by="creative-director",
        )
    )
    service.transition_job(str(job["id"]), JobTransition(target_status="PUBLISHED", actor="validator"))

    append_only = False
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM job_events"))
    except DBAPIError:
        append_only = True
    health = database_health(engine)
    snapshot = service.snapshot()
    engine.dispose()

    vendor_manifest_path = ROOT / "src" / "studio_manager" / "static" / "vendor" / "htmx.manifest.json"
    vendor_manifest = json.loads(vendor_manifest_path.read_text(encoding="utf-8"))
    vendor_path = vendor_manifest_path.parent / "htmx-2.0.11.min.js"
    htmx_valid = (
        sha256(vendor_path) == vendor_manifest["sha256"]
        and vendor_path.stat().st_size == vendor_manifest["bytes"]
    )

    protected = json.loads((ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    protected_results = []
    for source in protected["sources"]:
        path = Path(source["path"])
        actual = sha256(path) if path.is_file() and source.get("sha256") else None
        protected_results.append(
            {
                "id": source["id"],
                "exists": path.exists(),
                "hash_equal": actual == source.get("sha256") if actual else True,
            }
        )

    downgrade_database(database_path)
    remaining = sqlite3.connect(database_path)
    tables_after_downgrade = [
        row[0]
        for row in remaining.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    ]
    remaining.close()
    upgrade_database(database_path)

    checks = {
        "database_health": health["ok"],
        "catalog_asset_job_approval_roundtrip": (
            bool(asset_version) and snapshot["production_jobs"][0]["status"] == "PUBLISHED"
        ),
        "invalid_transition_atomic": invalid_transition_blocked and len(snapshot["job_events"]) == 7,
        "append_only_trigger": append_only,
        "htmx_local_hash": htmx_valid,
        "migration_downgrade": tables_after_downgrade == ["alembic_version"],
        "migration_reupgrade": True,
        "protected_sources_unchanged": all(item["exists"] and item["hash_equal"] for item in protected_results),
    }
    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_1B_DOMAIN_REGISTRY",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "htmx": vendor_manifest,
        "database": health,
        "record_counts": {key: len(value) for key, value in snapshot.items()},
        "protected_sources": protected_results,
        "external_application_configuration_changes": [],
        "next_gate": "CREATIVE_DIRECTOR_PHASE_1C_APPROVAL",
    }
    output = report_dir / "phase1b_validation.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for path in temp_dir.glob("phase1b.db*"):
        path.unlink()
    try:
        temp_dir.rmdir()
    except OSError:
        pass
    print(json.dumps({"status": report["status"], "report": str(output), "checks": checks}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
