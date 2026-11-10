from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePath

from studio_manager.service import DomainError


@dataclass(frozen=True, slots=True)
class StoredFile:
    relative_path: str
    absolute_path: str
    sha256: str
    size_bytes: int


class LocalStorageService:
    def __init__(self, root: Path):
        original = root.absolute()
        if original.is_symlink():
            raise DomainError("managed storage root must not be a symlink", 500)
        original.mkdir(parents=True, exist_ok=True)
        self.root = original.resolve(strict=True)

    def _target(self, relative_path: str) -> Path:
        value = PurePath(relative_path)
        if value.is_absolute() or not value.parts or any(part in {"", ".", ".."} for part in value.parts):
            raise DomainError("storage path must be a safe relative path")
        target = self.root.joinpath(*value.parts)
        current = self.root
        for part in value.parts[:-1]:
            current = current / part
            if current.exists() and current.is_symlink():
                raise DomainError("storage path crosses a symlink")
        resolved = target.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise DomainError("storage path escapes managed root")
        if target.exists() and target.is_symlink():
            raise DomainError("storage target must not be a symlink")
        return target

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def write_bytes(self, relative_path: str, data: bytes) -> StoredFile:
        target = self._target(relative_path)
        if target.exists():
            raise DomainError("managed file already exists", 409)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.parent.resolve(strict=True).is_relative_to(self.root):
            raise DomainError("storage parent changed during write")
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError as exc:
                raise DomainError("managed file already exists", 409) from exc
        finally:
            temporary.unlink(missing_ok=True)
        return StoredFile(
            relative_path=target.relative_to(self.root).as_posix(),
            absolute_path=str(target),
            sha256=self.sha256(target),
            size_bytes=target.stat().st_size,
        )

    def read_bytes(self, relative_path: str) -> bytes:
        target = self._target(relative_path)
        if not target.is_file():
            raise DomainError("managed file not found", 404)
        return target.read_bytes()

    def delete(self, relative_path: str) -> None:
        target = self._target(relative_path)
        target.unlink(missing_ok=True)
