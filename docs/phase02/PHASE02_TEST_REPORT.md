# Phase 02 Test Report

Date: 2026-11-01  
Overall: **PASS**

## Automated regression

- `uv run --frozen ruff check src tests migrations scripts/phase02`: PASS.
- `uv run --frozen pytest -W error --cov=studio_manager`: 37 PASS.
- Total application coverage: 89% across 904 statements.
- Phase 0 health: PASS, including backup/restore and protected hashes.
- Phase 0 foundation, Phase 1A, Phase 1B, and Phase 02 validators: PASS.

## Gateway coverage

- Nested method selection, default deny, explicit deny, scope enforcement, approval matching, concurrency, timeout/retry, rollback, redaction, and invocation persistence are covered by `tests/test_phase02_gateway.py`.
- Adapter failures retain a chained internal cause for local evidence while the public DomainError remains bounded.

## Application integrations

- Blender isolated MCP run: PASS; read/write/read sequence and `.blend`, `.glb`, `.png` outputs verified.
- Unreal PinWright run: PASS; identity, level creation, import, saves, spawn, Sequencer operations, and viewport capture all succeeded through the gateway.
- Unreal deterministic reset/recreation: PASS on a subsequent full run.

## Safety checks

- Protected SHA-256 values unchanged.
- Global Blender preferences unchanged from the pre-integration baseline.
- No public listener, rejected MCP, C++ toolchain, or protected-project write was introduced.

Machine-readable evidence is under `storage/80_REPORTS/`.
