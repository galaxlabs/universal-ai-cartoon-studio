# Phase 02 MCP Gateway and Registry

## Implemented controls

- Argument-aware operation selection for `tool`, nested `method`, or nested `action` servers.
- Default-deny allow/deny patterns with explicit write and approval classifications.
- Loopback-only server registration and managed write scopes under `storage/10_DEVELOPMENT` or `storage/20_TEMP`.
- Per-operation approvals, bounded concurrency, timeouts, retries, rollback callbacks, sanitized argument evidence, and persistent invocation records.
- Migration: `0003_mcp_gateway`; production database upgraded successfully.

## Approved servers

- Blender: `ahujasid/mcp-for-blender` 2.2.6, commit `992233bb258975a05eec8b5691465c50c2831e34`, safe mode, `127.0.0.1:9876`, isolated profile only.
- Unreal: PinWright 1.0.0, commit `20de4b5d6f18e9839aca17cc732fd6ef0a54a260`, bearer-authenticated loopback HTTP, project-derived port `25364`, isolated UE project only.

## Rejected servers

- Blender Orchestrator: rejected for missing license evidence, unauthenticated broad writes, and port conflict.
- GenOrca Unreal MCP: rejected for unauthenticated TCP and nested arbitrary Python.

## Evidence

- API and gateway: `src/studio_manager/api.py`, `src/studio_manager/mcp_gateway.py`.
- Tests: `tests/test_phase02_gateway.py`.
- Machine evidence: `mcp_gateway_policies`, `mcp_invocations`, and `audit_events` in `studio.db`.
