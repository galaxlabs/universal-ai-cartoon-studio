# Phase 03-A Security

## Implemented controls
- Loopback-only binding and trusted-host middleware.
- Bearer authentication on every `/api/v1` route and an additional write-intent header on mutations.
- Local principal identity replaces caller-supplied audit actors for jobs, transitions, and approvals.
- No unrestricted CORS.
- Pydantic length, pattern, enum, frame-range, pagination, and hash validation.
- Bound SQL values and server-side allow-lists for every dynamic table, column, and filter.
- Restrictive business deletion and append-only approval/audit/job evidence.
- Approved/published asset versions are immutable; direct approved-version creation is rejected.
- Storage rejects absolute paths, traversal, root/component/target symlinks, and existing targets. Same-directory temporary writes are flushed and promoted through create-only hard links.
- Import paths are exact allow-listed Phase 02 sources; source hashes and target fingerprints detect drift.
- Backups are written to temporary files, integrity-tested, atomically promoted, hash-registered, and verified again before confined recovery.
- Protected Blender sources remain outside managed write scopes and their hashes pass final validation.

## Residual boundaries
- Legacy `/api` routes are retained for Phase 02 compatibility and use loopback plus the Studio write-intent header rather than bearer authentication. New integrations must use `/api/v1`.
- SQLite permits one writer; WAL and busy timeout support concurrent readers/background access but do not turn SQLite into a multi-writer server.
- The token is a local application secret, not a remote identity platform. Multi-user role enforcement is deferred.
- Database backup does not copy the whole managed binary corpus. Binary recovery relies on external managed-file backups plus database hashes.
- Filesystem confinement defends normal and concurrent application access; an administrator who can replace directories or alter process permissions remains outside the application threat boundary.

## Explicitly absent
- Public listener, permissive CORS, arbitrary shell/Python endpoints, arbitrary job execution, automatic MCP activation, and protected-project write access.
