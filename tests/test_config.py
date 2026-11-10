from __future__ import annotations

from pathlib import Path

import pytest

from studio_manager.config import Settings


def test_non_loopback_host_is_rejected(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "db.sqlite", host="0.0.0.0", test_mode=True)  # noqa: S104
    with pytest.raises(ValueError, match="127.0.0.1"):
        settings.validate()


def test_privileged_port_is_rejected(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "db.sqlite", port=80, test_mode=True)
    with pytest.raises(ValueError, match="unprivileged"):
        settings.validate()
