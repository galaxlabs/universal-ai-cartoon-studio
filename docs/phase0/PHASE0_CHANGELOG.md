# Phase 0 Changelog

## Created
- Isolated Studio root and D-drive storage zones.
- Project safety rules and protected-source registry.
- Master requirements, architecture, two ADRs and threat model.
- Component decision manifest and SQLite v0.1 schema.
- Read-only discovery report and rollback instructions.
- Deterministic machine/protected-source/SQLite health check.
- Foundation validator and generated JSON/Markdown test reports.

## Installed or enabled
- No Studio runtime dependency installed.
- No Blender addon installed or enabled.
- No Unreal plugin or project installed or enabled.
- No firewall, security, network or external application setting changed.

## Recorded side effect
- A discovery-only `pnpm --version` probe caused Corepack to cache pnpm 12.16.1. It created no project configuration and pnpm is not selected for Phase 1.

## Validation
- All health checks passed.
- All foundation checks passed.
- SQLite created 23 schema tables with foreign keys enabled.
- Simulated failed transaction rolled back correctly.
- SQLite backup opened and restored the expected data, then test artifacts were removed.
- All registered protected-file SHA-256 hashes matched before the approval gate.
