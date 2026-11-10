# Phase 03-A Test Plan and Evidence

## Automated coverage
- Schema registration for all required SQLAlchemy models.
- Alembic base upgrade, `0004` downgrade, re-upgrade, integrity, and Phase 02 evidence preservation.
- Bearer rejection, write-intent rejection, authenticated CRUD, filters, pagination, restrictive deletion, and audit generation.
- Character variants, persisted jobs, append-only approvals/audits, and non-executing job APIs.
- Asset-version lifecycle, approval requirements, direct-approved creation rejection, and approved-row immutability.
- Storage hash, create-only atomic write, traversal rejection, absolute-path rejection, root/component symlink rejection, and cleanup.
- Skills/report dry runs, live imports, repeated-import skips, unknown-field evidence, source allow-listing, and manual-change conflicts.
- Online backup, registered SHA-256, integrity/reopen, confined restore copy, and tamper rejection.
- Existing worker, MCP gateway, UI, catalog, and protected-source regressions.

## Executed evidence
- Ruff on current source, tests, migrations, active Phase 01-03 scripts: PASS.
- Pytest with warnings as errors: 46 PASS.
- Application coverage: 89%.
- Phase 0 health/foundation validators: PASS.
- Phase 1A and Phase 1B validators: PASS.
- Phase 02 validator: PASS.
- Phase 03-A validator: PASS.
- Protected-source test and validator hashes: PASS.

## Evidence files
- `storage/80_REPORTS/phase03a_pre_migration_backup.json`
- `storage/80_REPORTS/phase03a_phase02_import.json`
- `storage/80_REPORTS/phase03a_backup_recovery.json`
- `storage/80_REPORTS/phase03a_validation.json`

## Known verification limitation
The workspace has no Git metadata, so Git diff/status/history evidence is unavailable. File-level tests, database evidence, source hashes, and validators are used instead.
