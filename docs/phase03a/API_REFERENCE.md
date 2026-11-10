# Phase 03-A API Reference

## Authorization
- All `/api/v1` routes require `Authorization: Bearer <local token>`.
- State-changing requests also require `X-Studio-Request: 1` as explicit write intent.
- `scripts/run_local.py` uses one application instance and prints the active token only to the local console. `STUDIO_API_TOKEN` may provide a stable token of at least 24 characters.
- No unrestricted CORS middleware is enabled.

## Pagination and filters
- Collection responses contain `items`, `count`, `limit`, and `offset`.
- `limit` is 1-100; `offset` is non-negative.
- Filters are exact-match and table-specific; dynamic SQL identifiers come only from server allow-lists.

## Routes
- Projects: `GET/POST /api/v1/projects`, `GET/PATCH/DELETE /api/v1/projects/{id}`; filter by status.
- Assets: `GET/POST /api/v1/assets`, `GET/PATCH/DELETE /api/v1/assets/{id}`; filter by project, type, and lifecycle.
- Asset versions: `GET/POST /api/v1/assets/{id}/versions`; lifecycle via `POST /api/v1/asset-versions/{id}/transitions`.
- Characters: `GET/POST /api/v1/characters`, `GET/PATCH/DELETE /api/v1/characters/{id}`.
- Variants: `GET/POST /api/v1/characters/{id}/variants`, `PATCH/DELETE /api/v1/character-variants/{id}`.
- Jobs: `GET/POST /api/v1/jobs`, `GET /api/v1/jobs/{id}`, and lifecycle-only `POST /api/v1/jobs/{id}/transitions`.
- Approvals: `GET/POST /api/v1/approvals`, `GET /api/v1/approvals/{id}`. Approval records are append-only.
- Audit: `GET /api/v1/audit-events`, `GET /api/v1/audit-events/{id}`. Audit records are append-only.
- Imports: `GET/POST /api/v1/imports`.
- Backups: `GET/POST /api/v1/backups`.

## Lifecycle and deletion rules
- Asset versions start as `DRAFT`, transition through validation and pending approval, and require SHA-256 plus an existing managed workspace before approval.
- The authenticated principal overrides caller-supplied job, transition, and approval actor names.
- Deletes reject protected assets and records with dependents; no endpoint silently cascades business deletion.
- Jobs are persisted and transitioned only. This API does not execute arbitrary jobs.

## Compatibility route
Legacy `/api` routes remain for the existing Phase 01/02 local UI and tests. They remain loopback-only and require the Studio write-intent header, but they are not the new bearer-authenticated Phase 03-A contract.
