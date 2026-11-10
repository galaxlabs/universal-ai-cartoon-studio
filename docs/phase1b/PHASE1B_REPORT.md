# Phase 1B — Catalog, Assets, Jobs, Approvals and HTMX Report

## Result
Phase 1B passed. The Studio now has a functional catalog registry, asset-version tracking, durable job state machines with append-only evidence, approval workflows, and a locally vendored HTMX management UI.

## New components
- **HTMX 2.0.11** vendored from pinned upstream commit `fa978b24e75fb03c137bf2cdae4fef0e711cf8a1`. SHA-256 verified: `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`. License: 0BSD.
- **python-multipart** 0.0.32 for form parsing.

## Implemented domains

### Catalog
- Projects, series, episodes, scenes, shots with parent foreign keys and unique codes.
- Characters, assets, asset versions with version auto-increment.
- Duplicate and missing-parent records return 409.
- All records include deterministic audit events.

### Security invariants
- Every state-changing request requires the `X-Studio-Request: 1` header; missing headers return 403.
- `TrustedHostMiddleware` rejects untrusted `Host` headers with 400.
- Workspace paths must be absolute and resolve inside `storage/10_DEVELOPMENT` or `storage/20_TEMP`. Protected root paths are rejected with 400.
- CSP includes `script-src 'self'` and `connect-src 'self'`.

### Jobs
- 11-state machine with guarded transitions: `DRAFT → QUEUED → RUNNING → VALIDATING → PENDING_APPROVAL → APPROVED → PUBLISHED`, plus `FAILED`, `BLOCKED`, `CANCELLED`, `ROLLED_BACK`.
- Invalid transitions fail atomically at 409 with no events written.
- Monotonic append-only job events via SQLite triggers.

### Approvals
- Approval decisions against jobs require `PENDING_APPROVAL` status; invalid subjects return 409.
- APPROVED transitions to `APPROVED`; REJECTED/CHANGES_REQUESTED transitions to `BLOCKED`.
- All decisions are append-only with triggers.

### Append-only evidence
- SQLite triggers on `job_events`, `approvals`, and `audit_events` prevent UPDATE and DELETE.
- Attempted writes through the engine raise DBAPIError with an append-only message.

### UI
- `/workspace` page with HTMX-driven forms for projects, assets, jobs, transitions, and approvals.
- Partial rendering via `partials/workspace_content.html`.
- HTMX served from local vendor path; no CDN dependency.

## Verification evidence
- Ruff: PASS.
- Pytest: 14 tests PASS with warnings treated as errors.
- Application code coverage: 97% (426 statements, 14 missed defensive branches).
- Migration upgrade through 0002, downgrade to base, re-upgrade: PASS.
- Real Uvicorn process smoke test: health PASS (`ok`, `127.0.0.1`), workspace PASS (200, "Production registry"), HTMX PASS (200, 52182 bytes).
- Standalone Phase 1B validator: PASS (8 checks).
- Protected-source hashes: PASS.
- Real foundation database backed up before migration: PASS (`integrity_check: ok`, migration `0001_phase0_schema`).

## Corrected during testing
- CSP `style-src 'self'` blocked HTMX v2's runtime inline styles in the browser. `style-src` now includes `'unsafe-inline'`; `script-src` stays `'self'` only, and no CDN or remote origin is permitted. Regression assertions were added to `tests/test_app.py`.
- Job transition event sequence count test corrected: approval triggers an additional event, so 7 events expected (not 6).
- HTMX partial test corrected: partial response should not contain `<html>` or `<body>` tags (not `workspace-content` attribute check).
- Ruff `B008` resolved by using `Annotated[StudioService, Depends(service)]` type alias instead of `= Depends(service)` defaults.
- Ruff `S608` suppressed with `# noqa: S608` for safe allow-listed table name injection.

## Known limitations and next gate
- No background worker, Blender adapter, Unreal adapter or MCP integration is active.
- No file import, render, generation or transfer is implemented.
- No authentication; the service remains loopback-only and single-user.
- The UI is foundation-only; production-oriented workflows and dashboards are deferred.
- Creative Director approval is required before Phase 1C worker/adapter implementation.
