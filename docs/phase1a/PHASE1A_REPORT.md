# Phase 1A — Local Application Foundation Report

## Result
Phase 1A passed. The Studio now has an isolated, locked Python application foundation on D: and remains disconnected from Blender, Unreal and MCP automation.

## Installed runtime and direct components
- CPython 3.13.13, managed inside `.python/`.
- Project environment in `.venv/`.
- FastAPI 0.162.0 (MIT).
- Uvicorn 0.54.0 (BSD-3-Clause).
- Jinja 3.1.6 (BSD-3-Clause).
- SQLAlchemy 2.1.6 (MIT).
- Alembic 1.20.1 (MIT).
- Development tools: pytest 9.2.0, pytest-cov 7.1.0, httpx2 2.16.0 and Ruff 0.17.3.
- Exact direct and transitive versions are recorded in `uv.lock`.

## Implemented foundation
- FastAPI application factory and local dashboard.
- Hard-coded `127.0.0.1:8765` startup boundary and trusted-host enforcement.
- API documentation endpoints disabled in this phase.
- No CORS configuration and no public listener.
- Security headers: no-store, restrictive CSP, no-referrer, nosniff and frame denial.
- SQLite connection enforcement: foreign keys, WAL, `synchronous=FULL` and 5000 ms busy timeout.
- Alembic baseline for the approved 23-table Phase 0 schema.
- Upgrade, downgrade and re-upgrade support.

## Verification evidence
- Ruff: PASS.
- Pytest: 7 tests PASS with warnings treated as errors.
- Application code coverage: 99% (110 statements, one defensive branch not executed).
- Alembic upgrade/downgrade/re-upgrade: PASS.
- Real Uvicorn process request to `http://127.0.0.1:8765/api/health`: PASS.
- Post-smoke-test listener check: no listener remained.
- Protected-source hashes: PASS.
- Phase 1A deterministic validator: PASS.

## Disk impact after package-cache cleanup
- `.venv`: 75,146,972 bytes.
- `.python`: 63,732,437 bytes.
- SQLite foundation database: 299,008 bytes.
- Remaining uv cache metadata: 2,128 bytes; 96.9 MiB download cache removed.

## Corrected during testing
- Alembic SQLite PRAGMAs initially opened an implicit transaction, preventing persistence of the version row. An explicit commit was added before migration context setup.
- Test temporary files initially used the Windows C: temp directory. Pytest now uses `storage/20_TEMP/pytest` on D: and cleans it after the session.
- Starlette deprecated the old `httpx` fallback. The locked development dependency was replaced with supported `httpx2` 2.16.0.
- Alembic's legacy `prepend_sys_path` parsing warning was removed by setting `path_separator=os`.

## Known limitations and next gate
- The dashboard is foundation-only; production catalog modules and write workflows are not implemented.
- HTMX remains selected but not vendored because Phase 1A has no interactive workflow requiring it.
- Authentication is absent because the service is loopback-only and single-user; public or remote access remains prohibited.
- No background worker, Blender adapter, Unreal adapter or MCP integration is active.
- Creative Director approval is required before Phase 1B domain implementation.
