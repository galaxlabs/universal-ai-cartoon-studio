# Phase 03-A Migration Notes

## Baseline
- Pre-change revision: `0003_mcp_gateway`.
- Pre-change integrity: `ok`; 26 tables.
- Consistent backup: `storage/60_BACKUPS/phase03a/studio-pre-phase03a-20261101-075024.db`.
- Backup SHA-256: `a68ac405ec2188aad3139f710751a45b4dcd0821a003973854af6517fca9211b`.
- Full baseline: `PRE_CHANGE_BASELINE.md` and `storage/80_REPORTS/phase03a_pre_migration_backup.json`.

## Forward migration
`0004_phase03a_foundation` is additive. It creates character variants, import batches, import provenance, users, and application settings; adds indexes; and adds approved-version immutability triggers. Existing Phase 02 tables and rows are not rewritten.

## Verification
- Empty database upgrade: base -> `0004` yields 31 tables and integrity `ok`.
- Schema rollback: `0004` -> `0003` yields 26 tables and integrity `ok`.
- Re-upgrade: `0003` -> `0004` returns to 31 tables and integrity `ok`.
- A dedicated test seeds Phase 02 approval and audit evidence before the forward migration, then confirms both survive upgrade and downgrade.

## Downgrade warning
Downgrading removes Phase 03-A-only tables and their records. Create and verify a current backup before any downgrade. The downgrade intentionally preserves all pre-existing Phase 02 tables and evidence but is not a data export for new Phase 03-A records.

## Live result
- Live revision: `0004_phase03a_foundation`.
- Integrity: `ok`.
- Phase 02 records imported with provenance; source files were not edited.
