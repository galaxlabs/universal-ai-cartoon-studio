# Phase 1A Rollback

No Blender, Unreal, MCP, firewall, operating-system security or protected asset configuration was changed.

## Application rollback
1. Stop `scripts/run_local.py` if it is running.
2. Preserve `storage/30_DATABASES/studio.db` and `storage/80_REPORTS/` if audit evidence is required.
3. To remove only installed runtime artifacts, delete project-local `.venv/` and `.python/`.
4. To remove the generated foundation database, delete `storage/30_DATABASES/studio.db`, `studio.db-wal` and `studio.db-shm` after explicit approval and after preserving any required backup.
5. Source rollback consists of removing Phase 1A application, migration, test and configuration files; do not alter the protected production root.

The dependency environment is reproducible from `pyproject.toml`, `.python-version` and `uv.lock` with `uv sync --frozen`.
