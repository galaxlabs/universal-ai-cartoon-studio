"""Run the documented quality gate in order and report each step.

Steps needing uv or the project venv are reported as SKIPPED when the tool is absent,
so a missing tool is never mistaken for a pass. Validators that need no network run last.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEP_TIMEOUT_SECONDS = 900
STEPS = [
    ("ruff", ["uv", "run", "--frozen", "ruff", "check", "src", "tests", "scripts", "migrations"]),
    ("pytest", ["uv", "run", "--frozen", "pytest", "-W", "error"]),
    ("phase03a_validator", ["uv", "run", "--frozen", "python", "scripts/phase03a/validate_phase03a.py"]),
    ("managed_manifest_verify", [sys.executable, "scripts/ops/managed_file_manifest.py",
                                 "--verify", "storage/80_REPORTS/managed_file_manifest.json"]),
]


def main() -> int:
    failed = False
    for name, command in STEPS:
        if shutil.which(command[0]) is None and command[0] != sys.executable:
            print(f"{name}: SKIPPED ({command[0]} not found)")
            continue
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False,
                                    timeout=STEP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            failed = True
            print(f"{name}: FAIL (timed out after {STEP_TIMEOUT_SECONDS}s; a tool may be waiting on network)")
            continue
        status = "PASS" if result.returncode == 0 else "FAIL"
        failed = failed or result.returncode != 0
        print(f"{name}: {status}")
        if result.returncode != 0:
            print(result.stdout[-800:], result.stderr[-800:])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
