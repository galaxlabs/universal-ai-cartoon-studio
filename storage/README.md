# Managed Storage Zones

- `00_PROTECTED_SOURCES`: registry pointers only; never copy or modify protected originals here.
- `10_DEVELOPMENT`: per-job editable workspaces.
- `20_TEMP`: disposable generated files.
- `30_VALIDATED`: assets that passed technical validation but are not approved masters.
- `40_APPROVED_MASTERS`: immutable approved versions promoted by recorded approval.
- `50_PUBLISHED_OUTPUTS`: released renders/packages.
- `60_BACKUPS`: database and pre-change backups with restore evidence.
- `70_LOGS`: redacted operational logs.
- `80_REPORTS`: machine-readable and human-readable validation evidence.
- `90_QUARANTINE`: untrusted downloads, failed imports and unapproved third-party integrations.
