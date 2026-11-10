from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("studio_desktop_launcher", ROOT / "scripts" / "launch_studio.py")
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


@pytest.fixture
def runtime_ready(monkeypatch):
    monkeypatch.setattr(launcher, "runtime_error", lambda: None)


def test_check_only_has_no_side_effects(monkeypatch, runtime_ready) -> None:
    process = MagicMock()
    browser = MagicMock()
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher, "open_workspace", browser)
    assert launcher.launch(check_only=True) == 0
    process.assert_not_called()
    browser.assert_not_called()


def test_existing_healthy_studio_reopens_without_process(monkeypatch, runtime_ready) -> None:
    process, browser = MagicMock(), MagicMock()
    monkeypatch.setattr(launcher, "studio_is_ready", lambda: True)
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher, "open_workspace", browser)
    assert launcher.launch() == 0
    browser.assert_called_once_with()
    process.assert_not_called()


def test_busy_port_does_not_kill_or_start_anything(monkeypatch, runtime_ready) -> None:
    process, browser = MagicMock(), MagicMock()
    monkeypatch.setattr(launcher, "studio_is_ready", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: True)
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher, "open_workspace", browser)
    assert launcher.launch() == 1
    process.assert_not_called()
    browser.assert_not_called()


def test_new_process_opens_only_after_ready(monkeypatch, runtime_ready) -> None:
    child = MagicMock()
    child.poll.return_value = None
    child.wait.return_value = 0
    process, browser = MagicMock(return_value=child), MagicMock()
    monkeypatch.setattr(launcher, "studio_is_ready", MagicMock(side_effect=[False, True]))
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: False)
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    monkeypatch.setattr(launcher, "open_workspace", browser)
    assert launcher.launch() == 0
    process.assert_called_once_with(
        [launcher.sys.executable, str(ROOT / "scripts" / "run_local.py")], cwd=ROOT
    )
    browser.assert_called_once_with()
    child.terminate.assert_not_called()


def test_child_failure_does_not_open_browser(monkeypatch, runtime_ready) -> None:
    child = MagicMock()
    child.poll.return_value = 1
    child.returncode = 1
    browser = MagicMock()
    monkeypatch.setattr(launcher, "studio_is_ready", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: False)
    monkeypatch.setattr(launcher.subprocess, "Popen", MagicMock(return_value=child))
    monkeypatch.setattr(launcher, "open_workspace", browser)
    assert launcher.launch() == 1
    browser.assert_not_called()


def test_health_identity_requires_correct_project(monkeypatch) -> None:
    payload = {"application": launcher.APPLICATION_ID, "project_id": launcher.PROJECT_ID,
               "status": "ok", "bind_host": "127.0.0.1"}
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    monkeypatch.setattr(launcher.OPENER, "open", MagicMock(return_value=response))
    assert launcher.studio_is_ready()
    payload["project_id"] = "another-project"
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    assert not launcher.studio_is_ready()


def test_health_connection_failure_is_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(launcher.OPENER, "open", MagicMock(side_effect=OSError("not listening")))
    assert not launcher.studio_is_ready()


def test_runtime_failure_does_not_install(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "runtime_error", lambda: "Runtime missing")
    process = MagicMock()
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    assert launcher.launch() == 1
    process.assert_not_called()


def test_timeout_stops_only_owned_child(monkeypatch, runtime_ready) -> None:
    child, stop = MagicMock(), MagicMock()
    monkeypatch.setattr(launcher, "studio_is_ready", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: False)
    monkeypatch.setattr(launcher.subprocess, "Popen", MagicMock(return_value=child))
    monkeypatch.setattr(launcher.time, "monotonic", MagicMock(side_effect=[0, 31]))
    monkeypatch.setattr(launcher, "stop_owned_process", stop)
    assert launcher.launch(browser=False) == 1
    stop.assert_called_once_with(child)
