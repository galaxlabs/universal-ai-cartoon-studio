"""Windows double-click entry point; no installation, public binding or worker activation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"
WORKSPACE_URL = BASE_URL + "/workspace"
APPLICATION_ID = "universal-ai-cartoon-studio"
PROJECT_ID = hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:16]
OPENER = build_opener(ProxyHandler({}))


def runtime_error() -> str | None:
    if sys.version_info[:2] != (3, 13):
        return "This project requires the prepared Python 3.13 Windows environment."
    packages = ("fastapi", "uvicorn", "sqlalchemy", "alembic", "jinja2", "multipart")
    missing = [name for name in packages if importlib.util.find_spec(name) is None]
    if missing:
        return "Runtime dependencies are missing: " + ", ".join(missing)
    return None


def studio_is_ready() -> bool:
    try:
        with OPENER.open(BASE_URL + "/api/health", timeout=1) as response:  # noqa: S310 -- fixed loopback URL
            payload = json.loads(response.read(65536))
        return (
            isinstance(payload, dict)
            and payload.get("application") == APPLICATION_ID
            and payload.get("project_id") == PROJECT_ID
            and payload.get("status") == "ok"
            and payload.get("bind_host") == HOST
        )
    except (OSError, ValueError, HTTPError, URLError):
        return False


def port_is_occupied() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            return True
    except OSError:
        return False


def open_workspace() -> None:
    if not webbrowser.open(WORKSPACE_URL, new=2):
        print(f"The browser did not open automatically. Open {WORKSPACE_URL} manually.")


def stop_owned_process(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return
    try:
        # Ctrl+C is also delivered to the child console; allow Uvicorn to shut down first.
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def launch(*, browser: bool = True, check_only: bool = False) -> int:
    problem = runtime_error()
    if problem:
        print(problem)
        return 1
    if check_only:
        print("Windows runtime ready. No server started and no browser opened.")
        return 0
    if studio_is_ready():
        print(f"Studio is already running: {WORKSPACE_URL}")
        if browser:
            open_workspace()
        return 0
    if port_is_occupied():
        print(f"Port {PORT} is busy or Studio is not healthy. No existing process was stopped.")
        print("If Studio is still starting, wait a few seconds and double-click again.")
        return 1
    print("Starting Universal AI Cartoon Studio...")
    print("Keep this window open while using Studio. Press Ctrl+C here to stop it.")
    # Fixed local script and current verified interpreter; never use shell=True or activate a worker.
    child = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "run_local.py")], cwd=ROOT)  # noqa: S603
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if child.poll() is not None:
                print("Studio exited before becoming ready. See the server message above.")
                return child.returncode or 1
            if studio_is_ready():
                print(f"Studio is ready: {WORKSPACE_URL}")
                if browser:
                    open_workspace()
                return child.wait()
            time.sleep(0.25)
        print("Studio did not become healthy within 30 seconds. Stopping only the process started here.")
        stop_owned_process(child)
        return 1
    except KeyboardInterrupt:
        print("\nStopping Studio...")
        stop_owned_process(child)
        return 0
    except Exception:
        stop_owned_process(child)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify runtime only; do not start or open anything")
    parser.add_argument("--no-browser", action="store_true", help="Start without opening a browser")
    args = parser.parse_args()
    try:
        return launch(browser=not args.no_browser, check_only=args.check)
    except OSError as exc:
        print(f"Could not launch Studio: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
