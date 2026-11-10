# Phase 03-B Handoff

## Implemented foundation available to Phase 03-B
- Authenticated `/api/v1` collections with exact filters and bounded pagination.
- Persistent production hierarchy, characters/variants, assets/versions, jobs, approvals, audit, imports, backups, users, and settings.
- Approval-gated asset-version lifecycle and immutable approved records.
- Stable source provenance for imported Phase 02 records.
- Secure create-only local storage and hash-verified database backup/recovery.
- Existing Jinja/HTMX UI and all Phase 02 worker/MCP integrations remain functional.

## Proposed Phase 03-B work, not implemented
- Frontend screens for hierarchy navigation, assets, variants, jobs, approvals, audit, imports, and backup status.
- Token bootstrap/user administration UX and role-aware local sessions.
- Managed binary upload/download workflows tied directly to `files` and `asset_versions`.
- Search, saved filters, optimistic UI concurrency, and background progress display.
- Full managed-file backup orchestration and retention policies.

## Required entry checks
1. Obtain explicit Phase 03-B approval.
2. Verify live revision `0004_phase03a_foundation` and `phase03a_validation.json` status `PASS`.
3. Create and verify a fresh database backup.
4. Preserve `/api/v1` authorization and lifecycle contracts.
5. Do not reintroduce generic execution, public binding, unrestricted CORS, cascade deletion, or protected-source writes.

## API compatibility notes
- Writes require both bearer authorization and `X-Studio-Request: 1`.
- Append-only records have no update/delete endpoints.
- Job routes persist and transition state; they do not execute arbitrary work.
- Legacy `/api` exists only for the current local UI and Phase 02 compatibility.
