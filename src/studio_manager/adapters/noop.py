"""Deterministic no-op adapter used to prove the worker pipeline end to end.

Runs in an isolated child process. It reads only two allow-listed environment
variables, verifies the workspace exists, and prints a JSON result. It never
executes user-supplied code and never writes outside the job workspace.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ADAPTER = "noop"
VERSION = "1.0"


def main() -> int:
    job_id = os.environ.get("STUDIO_JOB_ID", "")
    workspace_value = os.environ.get("STUDIO_WORKSPACE", "")
    if not job_id or not workspace_value:
        print(json.dumps({"ok": False, "error": "missing STUDIO_JOB_ID or STUDIO_WORKSPACE"}))
        return 2
    workspace = Path(workspace_value)
    if not workspace.is_dir():
        print(json.dumps({"ok": False, "error": "workspace is not a directory"}))
        return 3
    marker = workspace / "noop-adapter-result.json"
    payload = {
        "ok": True,
        "adapter": ADAPTER,
        "adapter_version": VERSION,
        "job_id": job_id,
        "workspace": str(workspace),
        "python": sys.version.split()[0],
    }
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
