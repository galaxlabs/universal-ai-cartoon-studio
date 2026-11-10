# Phase 0 Architecture

## Decision
Start as a local-first modular monolith rather than distributed services.

## Proposed application stack
- Python 3.13 managed by `uv` in a project-local environment — pending Phase 1 installation approval.
- FastAPI API and local server, bound to `127.0.0.1` only.
- Jinja templates plus a locally vendored HTMX build for the initial UI; no CDN dependency.
- SQLAlchemy 2.x and Alembic with SQLite in WAL mode.
- A single local worker process reading durable SQLite jobs; no Redis/Celery initially.
- Managed binary storage on D: with SHA-256 metadata in SQLite.

## Modules
- Studio catalog: projects, series, episodes, scenes and shots.
- Asset catalog: characters, environments, props, materials, rigs, animation cycles and versions.
- Integration registry: applications, MCP servers, skills, agents and allowlisted capabilities.
- Production: jobs, events, dependencies, outputs and retries.
- Quality: deterministic validation, visual-review evidence, approvals and change requests.
- Administration: component inventory, health state, backups, rollback and audit log.

## Blender adapter
- Deterministic inspection/build tasks use Blender background CLI with versioned scripts.
- Interactive tasks may use one approved MCP implementation, loopback only.
- Arbitrary code-execution tools are denied by default and require a named, approved job.
- Protected `.blend` files are opened read-only for inspection and never saved in place.

## Unreal adapter
- Use a new isolated Unreal project, never an existing production project.
- Prefer built-in Interchange, Control Rig, Sequencer Scripting, Python Editor Script Plugin and Editor Scripting Utilities.
- Use Unreal APIs for asset moves and edits; never move `.uasset` files with filesystem commands.
- Python is editor-only and experimental in UE 5.8, so every automated operation requires an isolated project test and evidence.

## Job state machine
`DRAFT -> QUEUED -> RUNNING -> VALIDATING -> PENDING_APPROVAL -> APPROVED -> PUBLISHED`

Failure states are `FAILED`, `BLOCKED`, `CANCELLED` and `ROLLED_BACK`. Approval and publish transitions are append-only audit events.

## Concurrency
Initial mode is single-user and single write-job per target application. SQLite is sufficient. PostgreSQL is deferred until measured concurrent writers or remote deployment justify it.
