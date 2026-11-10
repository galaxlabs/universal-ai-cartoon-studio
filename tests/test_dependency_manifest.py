from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_direct_application_dependencies_are_declared_and_locked() -> None:
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    direct = {re.split(r"[<>=!~\[; ]", requirement)[0] for requirement in manifest["project"]["dependencies"]}
    required = {"alembic", "fastapi", "jinja2", "pydantic", "python-multipart", "sqlalchemy", "starlette", "uvicorn"}
    assert required <= direct
    locked = {package["name"] for package in lock["package"]}
    assert direct <= locked


def test_setup_preserves_lock_and_uses_separate_windows_environment() -> None:
    setup = (ROOT / "Setup Studio.cmd").read_text(encoding="utf-8")
    assert "uv sync --frozen --python 3.13" in setup
    assert "UV_PROJECT_ENVIRONMENT=%~dp0.venv-windows" in setup
    assert "uv lock" not in setup
    assert "pip install" not in setup
