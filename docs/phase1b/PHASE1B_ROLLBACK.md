# Phase 1B Rollback

No Blender, Unreal, MCP, firewall, operating-system security or protected asset configuration was changed.

## Migration rollback
```powershell
uv run --frozen alembic downgrade 0001
```

This removes the append-only triggers. Data in `job_events`, `approvals` and `audit_events` remains intact but is no longer guarded by database triggers.

## Application rollback
1. Stop `scripts/run_local.py` if it is running.
2. Preserve `storage/30_DATABASES/studio.db` and `storage/80_REPORTS/` if audit evidence is required.
3. Remove Phase 1B files:
   - `src/studio_manager/contracts.py`
   - `src/studio_manager/service.py`
   - `src/studio_manager/api.py`
   - `src/studio_manager/ui.py`
   - `src/studio_manager/templates/workspace.html`
   - `src/studio_manager/templates/partials/`
   - `migrations/versions/0002_append_only_evidence.py`
   - `tests/test_phase1b_domains.py`
   - `scripts/phase1b/`
4. Revert `pyproject.toml` to remove `python-multipart` dependency.
5. Optionally remove `src/studio_manager/static/vendor/` to delete the vendored HTMX.
6. Do not alter the protected production root.

The pre-migration backup is at `storage/60_BACKUPS/phase1b/studio-pre-phase1b-*.db` and passed integrity check and open verification.
