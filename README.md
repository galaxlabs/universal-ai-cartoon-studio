# Universal AI Cartoon Studio Manager

Local-first production management and controlled automation for reusable Blender and Unreal Engine cartoon pipelines.

## Current state

Phase 03-A foundation is implemented: persistent catalog, approvals/audit, authenticated v1 API, source-specific imports and database backup/recovery, plus the existing local HTMX UI and Phase 02 worker/MCP integration foundation. This is not yet a complete visual flow editor or automatic film-production application. See project `ref/status.md` for dated evidence and outstanding gates.

## Windows: start without typing commands

Double-click **`Start Studio.cmd`** in this folder. It uses the prepared Windows environment, starts the loopback server and opens the workspace in your browser after a health check. Keep its console open; press **Ctrl+C** there to stop. Double-clicking again reopens a healthy existing Studio rather than starting another server.

See **`START_HERE_UR.md`** for Urdu instructions. No administrator privileges, background Windows service, auto-login startup or Blender/MCP activation is added.

On a new Windows computer, install [uv](https://docs.astral.sh/uv/getting-started/installation/), then double-click **`Setup Studio.cmd`** once before launching. This restores Python 3.13 and the locked dependency environment without replacing a Linux `.venv`. `pyproject.toml` declares direct dependencies; **`uv.lock` must travel with it** for exact transitive versions. Production data/binaries require separate verified backups.

Full dated implemented-versus-planned status: **`PROJECT_STATUS_UR.md`**.

## Repository-wide lint

```powershell
uv run --frozen python -m ruff check src tests scripts migrations --statistics
```

CI uses this same full scope, including historical Phase 0 and operations helpers.
The older phase-specific verification commands below remain historical subsets.

## Safety boundary

- Canonical project root: `D:\Projects\06_Studio_Systems\Universal_AI_Cartoon_Studio`
- Compatibility project path: `E:\Projects\universal-ai-cartoon-studio`
- Protected production source: `D:\Projects\01_3D_Blender\Blender Project`
- All future generated work must use this project's `storage/10_DEVELOPMENT` or `storage/20_TEMP` zones.

## Phase 0 checks

```powershell
py scripts/phase0/health_check.py
py scripts/phase0/validate_foundation.py
```

See `docs/phase0/PHASE0_DISCOVERY_REPORT.md` and `config/components.manifest.json`.

## Run the local foundation

```powershell
uv run --frozen python scripts/run_local.py
```

Open `http://127.0.0.1:8765`. The host is intentionally not configurable to a public interface.

## Phase 1A verification

```powershell
uv run --frozen ruff check src tests scripts/run_local.py scripts/phase1a migrations
uv run --frozen pytest -W error --cov=studio_manager --cov-report=term-missing
uv run --frozen python scripts/phase1a/validate_foundation.py
```

See `docs/phase1a/PHASE1A_REPORT.md` and `storage/80_REPORTS/phase1a_foundation_validation.json`.

## Phase 1B verification

```powershell
uv run --frozen ruff check src tests scripts/run_local.py scripts/phase1a scripts/phase1b migrations
uv run --frozen pytest -W error --cov=studio_manager --cov-report=term-missing
uv run --frozen python scripts/phase1b/validate_phase1b.py
```

See `docs/phase1b/PHASE1B_REPORT.md` and `storage/80_REPORTS/phase1b_validation.json`.

## Run one worker cycle

```powershell
uv run --frozen python scripts/run_worker.py --once
```

Only `FOUNDATION_REVIEW` and `VALIDATION` use the deterministic noop adapter. Unknown job types are blocked.

## Phase 02 verification

```powershell
uv run --frozen ruff check src tests scripts/run_local.py scripts/run_worker.py scripts/phase1a scripts/phase1b scripts/phase02 migrations
uv run --frozen pytest -W error --cov=studio_manager --cov-report=term-missing
uv run --frozen python scripts/phase02/validate_phase02.py
```

See `docs/phase02/PHASE02_REPORT.md` and `storage/80_REPORTS/phase02_validation.json`.
