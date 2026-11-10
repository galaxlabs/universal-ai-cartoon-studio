# Phase 02 Import Mapping

## Source-specific adapters
- `PHASE02_SKILLS` accepts only `config/phase02.skills.json` and maps each skill to the typed `skills` table with `enabled=0`.
- `PHASE02_REPORT` accepts only `phase02_*.json` directly under `storage/80_REPORTS` and maps each file to `validation_reports` with its source path and byte SHA-256.
- No generic arbitrary JSON-to-table importer exists.

## Provenance and idempotency
- Every batch stores source kind, exact path, whole-file SHA-256, dry-run state, counts, status, evidence path, and timestamps.
- Every imported record stores source key/hash, target type/ID, and the fingerprint of the last imported database row.
- An identical repeat skips the record.
- A changed source updates only when the target still matches its last imported fingerprint.
- A manually changed or pre-existing target produces a conflict and rolls back target changes for that batch.
- Concurrent uniqueness conflicts are converted to deterministic import conflicts.

## Unknown fields
Fields not mapped into typed columns are written unchanged to `storage/80_REPORTS/imports/<batch>-unknown-fields.json`. Evidence writes are confined, create-only, hashed by the storage layer, and removed if an unexpected database failure prevents a batch record.

## Executed migration
- Sources: one skills manifest and four Phase 02 JSON reports.
- Imported typed records: 14 disabled skills and 4 validation reports.
- Provenance records: 18.
- Dry-run occurred before each live import.
- Immediate repeated imports skipped all 18 records, proving idempotence.
- Evidence: `storage/80_REPORTS/phase03a_phase02_import.json`.
- Source Phase 02 files were not edited by the importer.
