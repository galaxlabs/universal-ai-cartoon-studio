# Proposal: Shared Asset Identity Between Studio and Damascus (not approved, not implemented)

Status: PROPOSAL. Phase 03-B has not been approved. Nothing in this document changes code or data.

## Problem
Damascus shots and assets (V004, V006) are referenced by Studio's protected-source list with hashes,
but they have no matching asset or shot records in the Studio database. A decision on one side is
not visible on the other.

## Proposed model
1. Each external source gets a stable `source_key` (for example `damascus.s03.v006`) and a `kind`.
2. A new `external_references` table holds: `source_key`, `file_sha256`, `path_hint`, `evidence_class`
   (C0 to C4 from the Damascus convention), `approval_state`, `recorded_at`.
3. Existing `assets` and `asset_versions` link to a reference by foreign key, never by file path alone.
4. Approval records remain append-only. A changed hash creates a new reference row and never edits an old one.

## Rules carried over from both projects
- Protected files are read-only. Studio records hashes; it never writes to them.
- Evidence class and "not historical" tags are stored as data, not as free text.
- A reference marked approved cannot be silently replaced.

## Open questions for the Creative Director
- Should Damascus shots be imported as Studio shots, or only referenced?
- Is one shared approval queue wanted, or separate queues per project?
