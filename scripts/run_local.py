from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from studio_manager.config import default_settings  # noqa: E402
from studio_manager.main import create_app  # noqa: E402


def main() -> None:
    settings = default_settings()
    print(f"Local API bearer token: {settings.api_token}")  # noqa: T201
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        reload=False,
        access_log=True,
    )


if __name__ == "__main__":
    main()
