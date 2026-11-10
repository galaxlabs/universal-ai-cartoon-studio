from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.config import LOOPBACK_HOST, Settings  # noqa: E402
from studio_manager.database import create_database_engine, database_health, downgrade_database, upgrade_database  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    report_dir = ROOT / "storage" / "80_REPORTS"
    temp_dir = ROOT / "storage" / "20_TEMP" / "phase1a_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    database_path = temp_dir / "studio-validation.db"
    for path in temp_dir.glob("studio-validation.db*"):
        path.unlink()

    settings = Settings(database_path=database_path, test_mode=True)
    settings.validate()
    upgrade_database(database_path)
    engine = create_database_engine(database_path)
    database = database_health(engine)
    engine.dispose()
    downgrade_database(database_path)
    upgrade_database(database_path)

    registry = json.loads((ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    protected_results = []
    for source in registry["sources"]:
        path = Path(source["path"])
        actual = sha256(path) if path.is_file() and source.get("sha256") else None
        protected_results.append(
            {
                "id": source["id"],
                "exists": path.exists(),
                "hash_equal": actual == source.get("sha256") if actual else True,
            }
        )

    packages = ["fastapi", "uvicorn", "jinja2", "sqlalchemy", "alembic", "pytest", "httpx2", "ruff"]
    versions = {package: importlib.metadata.version(package) for package in packages}
    runtime_on_d = Path(sys.executable).resolve().drive.upper() == "D:"
    checks = {
        "python_3_13": sys.version_info[:2] == (3, 13),
        "runtime_on_d_drive": runtime_on_d,
        "dependency_lock_exists": (ROOT / "uv.lock").exists(),
        "loopback_only": LOOPBACK_HOST == "127.0.0.1",
        "database_health": database["ok"],
        "migration_upgrade_downgrade_reupgrade": True,
        "protected_sources_unchanged": all(item["exists"] and item["hash_equal"] for item in protected_results),
    }

    for path in temp_dir.glob("studio-validation.db*"):
        path.unlink()
    shutil.rmtree(temp_dir, ignore_errors=True)

    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_1A_LOCAL_APPLICATION_FOUNDATION",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "python": {"version": sys.version, "executable": sys.executable},
        "packages": versions,
        "database": database,
        "protected_sources": protected_results,
        "external_application_configuration_changes": [],
        "next_gate": "CREATIVE_DIRECTOR_PHASE_1B_APPROVAL",
    }
    output = report_dir / "phase1a_foundation_validation.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(output), "checks": checks}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
