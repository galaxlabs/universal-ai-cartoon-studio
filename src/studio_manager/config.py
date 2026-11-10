from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    database_path: Path = PROJECT_ROOT / "storage" / "30_DATABASES" / "studio.db"
    host: str = LOOPBACK_HOST
    port: int = DEFAULT_PORT
    test_mode: bool = False
    api_token: str = field(default_factory=lambda: os.environ.get("STUDIO_API_TOKEN") or secrets.token_urlsafe(32))

    def validate(self) -> None:
        if self.host != LOOPBACK_HOST:
            raise ValueError("Studio services must bind to 127.0.0.1")
        if not 1024 <= self.port <= 65535:
            raise ValueError("Studio port must be an unprivileged TCP port")
        if not self.database_path.is_absolute():
            raise ValueError("Studio database path must be absolute")
        if len(self.api_token) < 24:
            raise ValueError("Studio API token must contain at least 24 characters")


def default_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings
