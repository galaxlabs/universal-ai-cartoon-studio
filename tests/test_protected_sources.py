from __future__ import annotations

import hashlib
import json
from pathlib import Path

from studio_manager.config import PROJECT_ROOT


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_registered_protected_sources_are_unchanged() -> None:
    registry = json.loads((PROJECT_ROOT / "config" / "protected_sources.json").read_text(encoding="utf-8"))
    for source in registry["sources"]:
        path = Path(source["path"])
        assert path.exists(), source["id"]
        if source.get("sha256"):
            assert file_sha256(path) == source["sha256"], source["id"]
