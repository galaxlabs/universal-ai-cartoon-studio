# Phase 03-A Pre-change Baseline

Captured: 2026-11-01T07:50:24Z

## Repository state
- Workspace: `D:\Projects\06_Studio_Systems\Universal_AI_Cartoon_Studio`
- Git metadata: unavailable (`fatal: not a git repository`); this is recorded as an evidence limitation, not a database or source failure.
- Runtime contract: project-local CPython 3.13 through `uv`; `pyproject.toml` requires `>=3.13,<3.14`.
- Existing application: FastAPI modular monolith, SQLAlchemy 2.x, Alembic, Pydantic v2, SQLite WAL.

## Database state
- Database: `storage/30_DATABASES/studio.db`
- Alembic revision: `0003_mcp_gateway`
- Integrity check: `ok`
- User tables including `alembic_version`: 26
- Existing evidence rows: approvals 11, audit events 134, MCP policies 2, MCP invocations 57, MCP servers 2.
- Existing catalog, assets, versions, and production job tables contain zero rows.

## Consistent backup
- Method: SQLite online backup API.
- Backup: `storage/60_BACKUPS/phase03a/studio-pre-phase03a-20261101-075024.db`
- SHA-256: `a68ac405ec2188aad3139f710751a45b4dcd0821a003973854af6517fca9211b`
- Size: 413696 bytes
- Reopen/integrity test: PASS (`ok`)
- Evidence: `storage/80_REPORTS/phase03a_pre_migration_backup.json`

## Protected and Phase 02 baseline
- Protected Blender root remains read-only: `D:\Projects\01_3D_Blender\Blender Project`.
- Phase 02 final Ruff, 37-test, 89% coverage, validators, protected hashes, Blender integration, Unreal integration, cinematic, and deterministic recovery evidence are the regression baseline.
- Verified cinematic artifact SHA-256: `25d75c7bcd8d76405f2e8e9196efc92b70a0b582c6927fbd02196083fc11347c`.

## Implementation boundary
The next migration must evolve the existing schema from `0003_mcp_gateway`, preserve all current evidence, retain legacy endpoints, and add authenticated `/api/v1` behavior without arbitrary job or MCP execution.
