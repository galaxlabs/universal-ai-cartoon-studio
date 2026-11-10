# ARCHITECTURE DECISIONS — Phase 01

Scope: confirm or revise the architecture already implemented in Phases 0–1B. Decision style: choose the simplest design that reliably meets the requirement.

## ADR-01 — Keep the local modular monolith
**Decision:** retain FastAPI + server-rendered Jinja + vendored HTMX + SQLite/Alembic in one process, on D:.
**Rationale:** single user, single machine, 16 GB RAM, 4C/8T. Microservices, Redis, Celery, PostgreSQL and containers add operational cost with no measured benefit.
**Status:** Accepted, already implemented and tested.

## ADR-02 — Do not adopt React for now
**Decision:** no SPA build chain in the current phase.
**Rationale:** a React/Vite toolchain adds Node dependency surface, bundling, and a wider CSP/attack surface for a loopback single-user UI. HTMX already delivers the interactive forms.
**Revisit when:** a workflow demonstrably needs rich client state (e.g. timeline scrubbing over large datasets).

## ADR-03 — Local filesystem asset store with DB metadata
**Decision:** binary assets live in managed D: zones; SQLite stores path, SHA-256, size, zone and lifecycle state.
**Rationale:** simple, inspectable, backup-friendly; avoids a blob database.
**Guard:** path allow-list (development/temp only), protected roots rejected, SHA-256 required at promotion.

## ADR-04 — Process-isolated agent/job execution
**Decision:** every automation runs as a child process with explicit working directory, environment allow-list, timeout and captured stdout/stderr; no in-process `exec` of job payloads.
**Rationale:** contains crashes and privilege; keeps the web process responsive; produces auditable evidence.
**Status:** design approved, implementation deferred to Phase 1C.

## ADR-05 — Single durable worker, no external queue
**Decision:** one serialized worker polling SQLite for `QUEUED` jobs, with append-only `job_events`.
**Rationale:** SQLite WAL + one writer is sufficient for one user; Celery/Redis not justified.
**Guard:** one concurrent write job per target application (Blender/Unreal).

## ADR-06 — MCP connection management
**Decision:** MCP servers registered in the `mcp_servers` table with bind host, permissions, version and enabled flag; loopback only; capability allow-list; at most one write-capable Blender MCP.
**Rationale:** prevents duplicate write authority and makes third-party risk explicit.
**Status:** schema present; no server enabled by this phase.

## ADR-07 — Version tracking and audit logging
**Decision:** append-only `job_events`, `approvals`, `audit_events` enforced by SQLite triggers; approval-gated lifecycle.
**Rationale:** creative accountability is a hard requirement; DB-level immutability beats convention.
**Status:** implemented and tested (Phase 1B).

## ADR-08 — Workspace layout: reuse, do not duplicate
**Decision:** the canonical root remains `D:\Projects\06_Studio_Systems\Universal_AI_Cartoon_Studio`; the requested Phase-01 directory names are **mapped**, not duplicated:

| Requested | Actual location |
|---|---|
| `app/`, `backend/`, `frontend/` | `src/studio_manager/` (+ `templates/`, `static/`) |
| `configs/` | `config/` |
| `database/` | `storage/30_DATABASES/` |
| `projects/` | `storage/10_DEVELOPMENT/projects/` |
| `assets/` | `storage/10_DEVELOPMENT/assets/`, `30_VALIDATED/`, `40_APPROVED_MASTERS/` |
| `renders/` | `storage/50_PUBLISHED_OUTPUTS/` |
| `validation/` | `storage/80_REPORTS/` |
| `logs/` | `storage/70_LOGS/` |
| `backups/` | `storage/60_BACKUPS/` |
| `tests/`, `docs/` | `tests/`, `docs/` (exist) |
| `agents/`, `skills/`, `mcp/` | **not created yet** — proposed as `src/studio_manager/agents|skills|mcp` in Phase 1C |

**Rationale:** creating a second parallel tree would fork source of truth and confuse backups/validation.
**Status:** Proposed — requires owner approval before any new directory is created.

## ADR-09 — C++ toolchain remains optional
**Decision:** do not install MSVC/Windows SDK now.
**Rationale:** nothing in the approved Python-only pipeline needs compilation. Blender/UE binaries are prebuilt.
**Trigger to install:** a need to build a C++ Blender addon, a Python C extension, or a UE C++ module — with explicit approval.

## Rejected alternatives (summary)
| Alternative | Why rejected |
|---|---|
| PostgreSQL/Redis/Celery | No measured concurrency need; more services, more memory. |
| Docker | Optional per policy; not needed for a local single-user app. |
| React/Vite | Extra build + supply-chain + CSP surface. |
| Unlicensed Unreal MCP | Legal and staleness risk. |
| Two Blender MCP servers | Duplicate write authority. |
