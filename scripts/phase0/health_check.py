from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "storage" / "80_REPORTS"
TEMP_DIR = ROOT / "storage" / "20_TEMP" / "phase0_health"
BACKUP_DIR = ROOT / "storage" / "60_BACKUPS" / "phase0_health"


def run(command: list[str], timeout: int = 60) -> dict:
    try:
        # main() supplies fixed local discovery argv, never CLI/API request data.
        result = subprocess.run(  # noqa: S603 -- reviewed internal argv; explicit shell=False, no user interpolation
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            shell=False,
        )
        return {
            "ok": result.returncode == 0, "returncode": result.returncode,
            "stdout": result.stdout.strip(), "stderr": result.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_probe() -> dict:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    source = TEMP_DIR / "probe.db"
    backup = BACKUP_DIR / "probe-backup.db"
    sidecars = (
        source, backup, Path(f"{source}-wal"), Path(f"{source}-shm"), Path(f"{backup}-wal"), Path(f"{backup}-shm"),
    )
    for path in sidecars:
        path.unlink(missing_ok=True)
    con = sqlite3.connect(source)
    con.execute("PRAGMA foreign_keys=ON")
    journal_mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    con.execute("CREATE TABLE probe(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
    con.execute("INSERT INTO probe(value) VALUES(?)", ("baseline",))
    con.commit()
    rollback_ok = False
    try:
        con.execute("BEGIN")
        con.execute("INSERT INTO probe(value) VALUES(?)", ("must_rollback",))
        raise RuntimeError("simulated failure")
    except RuntimeError:
        con.rollback()
        rollback_ok = con.execute("SELECT COUNT(*) FROM probe").fetchone()[0] == 1
    target = sqlite3.connect(backup)
    con.backup(target)
    target.close()
    con.close()
    restored = sqlite3.connect(backup)
    restore_count = restored.execute("SELECT COUNT(*) FROM probe").fetchone()[0]
    restored.close()
    backup_hash = sha256(backup)
    for path in sidecars:
        path.unlink(missing_ok=True)
    for path in (TEMP_DIR, BACKUP_DIR):
        try:
            path.rmdir()
        except OSError:
            pass
    return {
        "ok": journal_mode.lower() == "wal" and rollback_ok and restore_count == 1,
        "sqlite_runtime": sqlite3.sqlite_version, "threadsafety": sqlite3.threadsafety,
        "journal_mode": journal_mode, "rollback_ok": rollback_ok, "restore_count": restore_count,
        "backup_sha256_before_cleanup": backup_hash,
        "test_artifacts_cleaned": not any(path.exists() for path in sidecars),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    paths = json.loads((ROOT / "config" / "studio.paths.json").read_text(encoding="utf-8"))
    protected = json.loads((ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    blender = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
    unreal = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe")
    unreal_build = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Build\Build.version")
    hardware_cmd = [
        "powershell.exe", "-NoProfile", "-Command",
        '$os=Get-CimInstance Win32_OperatingSystem;'
        '$cs=Get-CimInstance Win32_ComputerSystem;'
        '$cpu=Get-CimInstance Win32_Processor;'
        '$gpu=Get-CimInstance Win32_VideoController;'
        '$d=Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3";'
        '[pscustomobject]@{os=$os.Caption;build=$os.BuildNumber;'
        'ram=$cs.TotalPhysicalMemory;cpu=$cpu.Name;cores=$cpu.NumberOfCores;'
        'logical=$cpu.NumberOfLogicalProcessors;gpu=@($gpu.Name);'
        'disks=@($d|ForEach-Object{@{drive=$_.DeviceID;size=$_.Size;free=$_.FreeSpace}})}'
        '|ConvertTo-Json -Depth 5',
    ]
    hardware_result = run(hardware_cmd)
    hardware = None
    if hardware_result["ok"]:
        try:
            hardware = json.loads(hardware_result["stdout"])
        except json.JSONDecodeError:
            hardware_result["ok"] = False
    protected_results = []
    for item in protected["sources"]:
        path = Path(item["path"])
        result = {"id": item["id"], "path": str(path), "exists": path.exists(), "type": item["type"]}
        if path.is_file() and item.get("sha256"):
            actual = sha256(path)
            result.update({
                "expected_sha256": item["sha256"], "actual_sha256": actual,
                "hash_equal": actual == item["sha256"], "size_bytes": path.stat().st_size,
            })
        protected_results.append(result)
    sqlite_result = sqlite_probe()
    checks = {
        "project_root_matches_config": Path(paths["project_root"]).resolve() == ROOT.resolve(),
        "loopback_bind_only": paths["bind_host"] == "127.0.0.1" and paths["policy"]["allow_public_bind"] is False,
        "all_storage_zones_exist": all((ROOT / value).is_dir() for value in paths["storage"].values()),
        "blender_exists": blender.exists(),
        "unreal_exists": unreal.exists(),
        "unreal_build_manifest_exists": unreal_build.exists(),
        "hardware_discovery": hardware_result["ok"],
        "sqlite_backup_restore_and_rollback": sqlite_result["ok"],
        "protected_sources_exist": all(item["exists"] for item in protected_results),
        "protected_file_hashes_match": all(item.get("hash_equal", True) for item in protected_results),
    }
    tools = {
        "python": run([sys.executable, "--version"]),
        "git": run(["git", "--version"]),
        "uv": run(["uv", "--version"]),
        "node": run(["node", "--version"]),
        "ffmpeg": run(["ffmpeg", "-version"]),
        "nvidia": run([
            "nvidia-smi", "--query-gpu=name,driver_version,memory.total,compute_cap", "--format=csv,noheader",
        ]),
        "blender": run([str(blender), "--version"]) if blender.exists() else {"ok": False},
    }
    warnings = [
        "System Python 3.14.4 is discovery-only; proposed application runtime is isolated Python 3.13.",
        "The existing Blender user profile enables ahujasid/mcp-for-blender; it is not Studio-approved.",
        "Do not enable the second Blender MCP candidate until duplicate write authority is removed.",
        "C: has approximately 10.2 GiB free; project environments, caches and outputs should live on D:.",
        "The standalone sqlite3 CLI is absent; Python sqlite3 runtime is used and tested.",
        "A pnpm version probe triggered an unprivileged Corepack cache download; no project Node setup was created.",
    ]
    report = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_0_DISCOVERY",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "hardware": hardware,
        "tools": tools,
        "sqlite_probe": sqlite_result,
        "protected_sources": protected_results,
        "warnings": warnings,
        "configuration_changes": [],
        "installations_performed": [],
    }
    output = REPORT_DIR / "phase0_health.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(output), "checks": checks}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
