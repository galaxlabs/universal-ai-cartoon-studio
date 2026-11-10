"""Single durable job worker with process-isolated, allow-listed adapters."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, text

from studio_manager.config import PROJECT_ROOT
from studio_manager.contracts import JobTransition
from studio_manager.database import create_database_engine, upgrade_database
from studio_manager.service import DomainError, StudioService

# Only these job types may execute. Each maps to a fixed module; user input never
# chooses an arbitrary command line.
ADAPTER_ALLOWLIST: dict[str, str] = {
    "FOUNDATION_REVIEW": "studio_manager.adapters.noop",
    "VALIDATION": "studio_manager.adapters.noop",
}

ADAPTER_TIMEOUT_SECONDS = 60
MAX_CAPTURED_OUTPUT = 4000


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class Worker:
    def __init__(self, engine, service: StudioService | None = None):
        self.engine = engine
        self.service = service or StudioService(engine)

    def claim_next(self) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM production_jobs WHERE status='QUEUED' ORDER BY created_at, id LIMIT 1")
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            job_id = str(row["id"])
            updated = connection.execute(
                text(
                    "UPDATE production_jobs SET status='RUNNING', started_at=:started "
                    "WHERE id=:id AND status='QUEUED'"
                ),
                {"started": now_iso(), "id": job_id},
            )
            if updated.rowcount != 1:
                return None
            self._append_event(connection, job_id, "CLAIMED", {"actor": "worker"})
            StudioService._audit(connection, "worker", "CLAIM", "JOB", job_id, None, {"status": "RUNNING"})
            claimed = dict(row)
            claimed["status"] = "RUNNING"
            return claimed

    def _append_event(self, connection: Connection, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
        sequence = connection.execute(
            text("SELECT COALESCE(MAX(sequence),0)+1 FROM job_events WHERE job_id=:id"),
            {"id": job_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO job_events(job_id,sequence,event_type,payload_json,created_at) "
                "VALUES(:id,:sequence,:event,:payload,:created)"
            ),
            {
                "id": job_id,
                "sequence": sequence,
                "event": event_type,
                "payload": json.dumps(payload, sort_keys=True),
                "created": now_iso(),
            },
        )

    @staticmethod
    def child_environment(job: dict[str, Any]) -> dict[str, str]:
        """Minimal environment allow-list: no tokens, keys or user profile leakage."""
        env = {
            "STUDIO_JOB_ID": str(job["id"]),
            "STUDIO_WORKSPACE": str(job["workspace_path"]),
            "PYTHONPATH": str(PROJECT_ROOT / "src"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for key in ("SYSTEMROOT", "PATH", "TEMP", "TMP"):
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    def execute(self, module: str, job: dict[str, Any]) -> dict[str, Any]:
        workspace = Path(str(job["workspace_path"]))
        try:
            workspace.mkdir(parents=True, exist_ok=True)
        except OSError:
            return {"ok": False, "error_code": "WORKSPACE_INVALID", "duration_ms": 0}
        command = [sys.executable, "-m", module]
        started = time.monotonic()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(  # noqa: S603 - fixed command, no shell
                command,
                cwd=str(workspace),
                env=self.child_environment(job),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=ADAPTER_TIMEOUT_SECONDS,
                check=False,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error_code": "ADAPTER_TIMEOUT",
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        duration_ms = int((time.monotonic() - started) * 1000)
        stdout = (completed.stdout or "")[:MAX_CAPTURED_OUTPUT]
        stderr = (completed.stderr or "")[:MAX_CAPTURED_OUTPUT]
        result: dict[str, Any] = {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "adapter": module,
            "duration_ms": duration_ms,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
        }
        if not result["ok"]:
            result["error_code"] = "ADAPTER_FAILED"
        return result

    def _finish(self, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
        if result["ok"]:
            self.service.transition_job(
                job_id,
                JobTransition(target_status="VALIDATING", actor="worker", payload={"adapter": result["adapter"]}),
            )
            final = self.service.transition_job(
                job_id,
                JobTransition(
                    target_status="PENDING_APPROVAL",
                    actor="worker",
                    payload={"duration_ms": result["duration_ms"], "stdout": result["stdout"]},
                ),
            )
        else:
            final = self.service.transition_job(
                job_id,
                JobTransition(
                    target_status="FAILED",
                    actor="worker",
                    payload={"error_code": result.get("error_code"), "stderr": result.get("stderr", "")},
                ),
            )
            with self.engine.begin() as connection:
                connection.execute(
                    text("UPDATE production_jobs SET error_code=:code WHERE id=:id"),
                    {"code": result.get("error_code", "ADAPTER_FAILED"), "id": job_id},
                )
        return final

    def run_once(self) -> dict[str, Any]:
        job = self.claim_next()
        if job is None:
            return {"claimed": None, "status": "IDLE"}
        job_id = str(job["id"])
        module = ADAPTER_ALLOWLIST.get(str(job["job_type"]))
        if module is None:
            self.service.transition_job(
                job_id,
                JobTransition(
                    target_status="BLOCKED",
                    actor="worker",
                    payload={"reason": "job type is not in the adapter allow-list"},
                ),
            )
            with self.engine.begin() as connection:
                connection.execute(
                    text("UPDATE production_jobs SET error_code='UNSUPPORTED_JOB_TYPE' WHERE id=:id"),
                    {"id": job_id},
                )
            return {"claimed": job_id, "status": "BLOCKED", "reason": "UNSUPPORTED_JOB_TYPE"}
        result = self.execute(module, job)
        try:
            final = self._finish(job_id, result)
        except DomainError as exc:
            return {"claimed": job_id, "status": "ERROR", "reason": exc.message}
        return {"claimed": job_id, "status": str(final["status"]), "adapter_ok": bool(result["ok"])}

    def run_forever(self, poll_seconds: float = 2.0) -> None:
        while True:
            outcome = self.run_once()
            if outcome.get("claimed") is None:
                time.sleep(poll_seconds)


def build_worker(database_path: Path | None = None) -> Worker:
    path = database_path or (PROJECT_ROOT / "storage" / "30_DATABASES" / "studio.db")
    upgrade_database(path)
    return Worker(create_database_engine(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal AI Cartoon Studio worker")
    parser.add_argument("--once", action="store_true", help="process at most one queued job and exit")
    parser.add_argument("--poll", type=float, default=2.0, help="poll interval in seconds")
    parser.add_argument("--database", type=Path, default=None, help="override the SQLite database path")
    args = parser.parse_args()
    worker = build_worker(args.database)
    if args.once:
        print(json.dumps(worker.run_once()))
        return 0
    worker.run_forever(args.poll)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
