# Phase 03-A Schema Map

## Required domain mappings
- `Project` -> `projects`; stable text ID, unique name, status, managed root, UTC timestamps.
- `Series` -> `series`; required project foreign key and project/name uniqueness.
- `Episode` -> `episodes`; required series foreign key and series/code uniqueness.
- `Scene` -> `scenes`; required episode foreign key and episode/code uniqueness.
- `Shot` -> `shots`; required scene foreign key, scene/code uniqueness, frame range, and FPS.
- `Character` -> `characters`; required project foreign key and project/code uniqueness.
- `CharacterVariant` -> `character_variants`; required character foreign key, character/code uniqueness, JSON configuration, status, and timestamps.
- `Asset` -> `assets`; required project foreign key, project/code uniqueness, type, lifecycle, and protected flag.
- `AssetVersion` -> `asset_versions`; required asset foreign key, sequential version uniqueness, workspace path, SHA-256, status, and creation time.
- `Job` -> `production_jobs`; required project foreign key, type, status, target, workspace, actor, and lifecycle timestamps.
- `Approval` -> `approvals`; append-only subject decision evidence.
- `AuditEvent` -> `audit_events`; append-only before/after evidence.
- `ImportBatch` -> `import_batches`; source path/hash, dry-run flag, status, counts, evidence path, errors, and timestamps.
- `BackupRecord` -> existing `backups`; path, SHA-256, restore-test flag, subject, and timestamp.
- `User` -> `users`; username, display name, role, optional token hash, active flag, and timestamps.
- `AppSetting` -> `app_settings`; key, JSON value, and update time.
- `ImportRecord` -> `import_records`; source key/hash to target ID/fingerprint provenance.

## Added indexes
- Character variant lookup by character/status.
- Import batches by source/time.
- Import records by target kind/ID.
- Audit events by subject/time.
- Backups by creation time.

## Integrity controls
- Foreign keys are enabled on every application connection.
- Existing approvals, audit events, and job events remain append-only.
- Approved and published asset-version rows reject updates and deletes.
- Business deletes use restrictive foreign keys; no silent cascade deletion was added.
- The live schema has 31 user tables including `alembic_version` at `0004_phase03a_foundation`.
