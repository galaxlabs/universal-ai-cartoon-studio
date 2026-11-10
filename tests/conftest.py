from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studio_manager.config import Settings
from studio_manager.main import create_app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "studio-test.db"


@pytest.fixture
def client(database_path: Path) -> Iterator[TestClient]:
    settings = Settings(project_root=database_path.parent, database_path=database_path, test_mode=True)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def pytest_sessionfinish() -> None:
    project_root = Path(__file__).resolve().parents[1]
    shutil.rmtree(project_root / "storage" / "20_TEMP" / "pytest", ignore_errors=True)
