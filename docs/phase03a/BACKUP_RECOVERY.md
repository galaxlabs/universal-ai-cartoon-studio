# Phase 03-A Backup and Recovery

## Backup procedure
1. Use `POST /api/v1/backups` or `scripts/phase03a/verify_backup_recovery.py`.
2. The service uses SQLite's online backup API, so WAL state is copied as a consistent committed snapshot.
3. It writes a temporary database under `storage/60_BACKUPS/phase03a/`.
4. It opens the copy read-only, runs `PRAGMA integrity_check`, reads the migration revision, and only then atomically promotes it.
5. It records path, SHA-256, restore-tested state, and UTC creation time in `backups` plus append-only audit evidence.

## Recovery verification
- A backup must be inside managed backup storage, registered in the live database, and match its registered SHA-256.
- Recovery writes only a new file under `storage/20_TEMP/recovery/`; it cannot replace the live database.
- The recovery copy is integrity-checked and migration-checked before promotion.
- The verifier removes its disposable recovery copy after proving it can reopen.

## Offline live restore
1. Stop the application and every worker.
2. Preserve the current live database and WAL sidecars as incident evidence.
3. Verify the selected backup against its recorded SHA-256 and run the recovery-copy procedure.
4. Replace the live database only through an explicitly approved offline operation.
5. Start the application, run `validate_phase03a.py`, all prior phase validators, and protected-source checks.

## Verified result
- Pre-migration backup reopened at revision `0003_mcp_gateway` with integrity `ok`.
- Post-migration backup reopened at revision `0004_phase03a_foundation` with integrity `ok`.
- Restored copy SHA-256 matched the backup and the live database was not replaced.
- Evidence: `storage/80_REPORTS/phase03a_backup_recovery.json`.

## Scope
This procedure protects SQLite. Managed binary files require their own filesystem backup policy; their database records retain hashes for verification.
