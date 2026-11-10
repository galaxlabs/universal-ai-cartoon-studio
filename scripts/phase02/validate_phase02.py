from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.contracts import JobCreate, JobTransition, ProjectCreate  # noqa: E402
from studio_manager.database import create_database_engine, upgrade_database  # noqa: E402
from studio_manager.mcp_manager import MCPManager, MCPRegistration  # noqa: E402
from studio_manager.service import StudioService  # noqa: E402
from studio_manager.worker import Worker  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report_dir = ROOT / "storage" / "80_REPORTS"
    temp_dir = ROOT / "storage" / "20_TEMP" / "phase02_validation"
    database = temp_dir / "phase02.db"
    workspace = temp_dir / "job-workspace"
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    upgrade_database(database)
    engine = create_database_engine(database)
    service = StudioService(engine)
    project = service.create_project(ProjectCreate(name="Phase 02 Validation"))
    job = service.create_job(
        JobCreate(
            project_id=str(project["id"]),
            job_type="FOUNDATION_REVIEW",
            workspace_path=str(workspace),
            requested_by="phase02-validator",
        )
    )
    service.transition_job(str(job["id"]), JobTransition(target_status="QUEUED", actor="phase02-validator"))
    worker_result = Worker(engine).run_once()
    with engine.connect() as connection:
        job_row = dict(
            connection.execute(
                text("SELECT status,error_code FROM production_jobs WHERE id=:id"), {"id": job["id"]}
            ).mappings().one()
        )
        events = [
            dict(row)
            for row in connection.execute(
                text("SELECT sequence,event_type FROM job_events WHERE job_id=:id ORDER BY sequence"),
                {"id": job["id"]},
            ).mappings()
        ]

    manager = MCPManager(engine)
    readonly = manager.register(
        MCPRegistration(
            name="phase02-readonly",
            source_url="https://example.invalid/readonly",
            version="0.0.0-test",
            license="MIT",
            bind_host="127.0.0.1",
            permissions=["read_scene"],
        ),
        actor="phase02-validator",
    )
    broad = manager.register(
        MCPRegistration(
            name="phase02-broad",
            source_url="https://example.invalid/broad",
            version="0.0.0-test",
            license="MIT",
            bind_host="localhost",
            permissions=["read_scene", "execute_code"],
        ),
        actor="phase02-validator",
    )
    readonly_check = manager.activation_check(str(readonly["id"]))
    broad_check = manager.activation_check(str(broad["id"]))
    engine.dispose()

    template = (
        ROOT / "src" / "studio_manager" / "templates" / "partials" / "workspace_content.html"
    ).read_text(encoding="utf-8")
    main_source = (ROOT / "src" / "studio_manager" / "main.py").read_text(encoding="utf-8")
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

    checks = {
        "worker_claimed_job": worker_result["claimed"] == job["id"],
        "worker_reached_approval_gate": job_row["status"] == "PENDING_APPROVAL",
        "worker_error_clear": job_row["error_code"] is None,
        "worker_event_sequence": [event["sequence"] for event in events] == list(range(1, 6)),
        "adapter_marker_created": (workspace / "noop-adapter-result.json").is_file(),
        "mcp_registry_disabled": all(item["enabled"] == 0 for item in manager.list_servers()),
        "mcp_readonly_policy_preview": readonly_check["would_enable"] is True,
        "mcp_execute_code_denied": broad_check["would_enable"] is False,
        "mcp_activation_not_exposed": "not implemented" in str(readonly_check["note"]),
        "html_patterns_v_mode_safe": (
            "[A-Za-z0-9_-]+" not in template and template.count(r"[A-Za-z0-9_\-]+") == 2
        ),
        "htmx_style_csp_present": "style-src 'self' 'unsafe-inline'" in main_source,
        "protected_sources_unchanged": all(item["exists"] and item["hash_equal"] for item in protected_results),
    }
    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_02_WORKER_AND_MCP_MANAGER",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "worker_result": worker_result,
        "job_events": events,
        "mcp_policy": {"readonly": readonly_check, "broad": broad_check},
        "protected_sources": protected_results,
        "third_party_installed": [],
        "mcp_servers_enabled": [],
        "next_gate": "BLENDER_OR_UNREAL_ADAPTER_EXPLICIT_APPROVAL",
    }
    output = report_dir / "phase02_validation.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(json.dumps({"status": report["status"], "report": str(output), "checks": checks}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
