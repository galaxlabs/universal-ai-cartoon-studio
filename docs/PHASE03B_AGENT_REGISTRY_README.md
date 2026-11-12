# Phase 03-B — Inert Agent & Skills Registry

## Source provenance and scope
- Both supplied ZIPs contain the same five source/doc files byte-for-byte. The clean source ZIP SHA256 is `09297ca24501b5b01a69fc4f4edf34d15ed834c3dd83ed40a012979e98477dae`; original ZIP SHA256 is `3d697babf78fa76ef775546755b557b911df8d149446bda9f9d994232bc03b0b`.
- Integrated once, excluding wrapper directories and cached pyc. Hardened rather than duplicating or replacing the existing application.
- This is metadata registration, **not an agent runner**. No model calls, tool execution, paid generation, worker activation or publishing is introduced.
- Development branch only. No production database migration, approved-asset edit, Blender operation or PR merge is authorized/performed here.

## Schema and lifecycle
- Alembic `0005_agent_skills_registry`, parent `0004_phase03a_foundation`, adds four tables: studio_agents, studio_agent_versions, studio_skills, studio_skill_versions.
- Current development head has 35 tables including Alembic metadata; historical Phase03A revision0004 has31. Explicit historical migration tests remain pinned to0004; compatibility validators recognize known heads without removing preservation assertions.
- New definitions are disabled. Public API creates DRAFT version snapshots only. All version rows are immutable; edits create new numbered snapshots.
- No approve/retire/activate/update/delete/execution endpoints exist in this initial registry. Approval/retirement authority and enablement need a separate audited lifecycle, not a status mutation that defeats immutability.
- Production startup still upgrades to head as before: **do not deploy/run this branch against the actual production database without a separate verified backup and deployment approval**. This PR does not deploy or merge itself.

## Legacy coexistence
- Existing agents, skills and capabilities tables are not renamed, copied, replaced or automatically enabled.
- `GET /api/v1/skills/legacy` exposes imported legacy skills read-only with namespace `legacy-import`.
- New studio definitions/versions use namespace `studio`. `allowed_skills` must contain exact existing **studio skill-version IDs**, never a mutable skill code or legacy ID.
- A DRAFT skill reference is planning metadata, not approval for execution. No automatic mapping of imported instructions/permissions to execution grants.

## API
All routes use existing bearer auth. Writes also use existing `X-Studio-Request: 1` middleware. Actor is the authenticated local principal, not caller-supplied input.
- GET/POST `/api/v1/agents`
- GET/POST `/api/v1/agents/{agent_id}/versions`
- GET/POST `/api/v1/skills`
- GET `/api/v1/skills/legacy`
- GET/POST `/api/v1/skills/{skill_id}/versions`

Collections return items/count/limit/offset; limit1–100, offset>=0; unknown owner404; duplicates409; transient writer lock503.

Strict Pydantic inputs forbid actor/status/enabled spoofing. Instruction limits50k characters; reference lists50 entries with128-character identifiers; JSON metadata16KiB and nesting12 levels. JSON Schema draft2020-12 declarations validated using jsonschema; remote refs/dialects rejected without fetching. Output validation during real execution is future runner work. Validation errors do not echo instruction/config input.

`allowed_tools` and `model_profile` are bounded **requested metadata only**, not permissions or configured provider credentials. A future runner must intersect exact approved versions with real MCP/tool policies, scopes, budgets, output schema, idempotency/retries and approval evidence. Never execute a tool solely because its name was stored here.

## Transaction/audit safety
- `BEGIN IMMEDIATE` serializes short SQLite write transactions before version allocation; no network/file/tool work inside transactions.
- SQLAlchemy Core fixed table metadata and bound values replace dynamic SQL construction.
- Integrity conflicts become controlled409; busy writers503; rollback on failure.
- Definition audits contain actual disabled state and identifying metadata. Version audits contain owner/version/status/content hash, not raw instructions or config. Do not store provider keys or secrets in descriptive/config metadata; use future credential references instead.

## Verification performed in isolation
- Full existing suite plus registry tests:87 local tests, including local protected-source check; portable subset excludes that external-file check.
- Fresh test databases and a read-only-created production DB **copy**:0004 ->0005 ->0004 ->0005,35 ->31 ->35 tables, integrity ok, foreign_key_check empty.
- All30 pre-existing business/evidence tables' row fingerprints unchanged during the copy migration cycle; actual production DB fingerprint unchanged.
- New API routes, missing/invalid bearer, missing intent, schema/payload limits, unknown parent, conflict responses, pinned references, parallel version allocation, immutable snapshots, audit redaction and no-execution behavior tested.
- Original14 imported skills preserved; legacy read-only visibility tested with14 synthetic records; actual production data remains untouched.

Use an explicit disposable DB with `python scripts/phase03b/validate_registry.py --database <test-copy.db>`. This read-only validator has no default live DB path and performs no upgrade.

## Next module
Story Creator, Story Critic and Story Archive should consume exact registry version IDs through a separately reviewed runner/archive contract. They are not implemented by this PR. The existing worker adapter allowlist and MCP approval system must remain authoritative.
