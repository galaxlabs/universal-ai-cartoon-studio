# PHASE 02 INSTALLATION PLAN (proposal — not executed)

Rule for Phase 02: install only what is needed, from a verified source, with a recorded version, license, and rollback. Nothing below runs without explicit approval.

## A. Already satisfied (no installation needed)
| Capability | Current state |
|---|---|
| Python application runtime | CPython 3.13.13, project-local via uv — installed |
| Web/API/DB stack | FastAPI, Uvicorn, Jinja, SQLAlchemy, Alembic, SQLite — installed and tested |
| HTMX | 2.0.11 vendored, hash-verified |
| Blender | 5.2.2 LTS installed |
| Unreal Engine | 5.8.4 installed |
| Git / LFS / Node / FFmpeg | Installed |

## B. Recommended Phase 02 items (in priority order)

### B1. Single durable job worker (pure Python — no third-party install)
- **What:** one worker process that claims `QUEUED` jobs, runs allow-listed adapters, writes `job_events`.
- **Why:** turns the tested job state machine into real execution with process isolation.
- **Cost/risk:** no new dependency; SQLite single-writer discipline required.
- **Approval:** Phase 1C approval (already the declared next gate).

### B2. MCP connection manager (no server enabled)
- **What:** registry + permission model for `mcp_servers`/`capabilities`; loopback stdio/HTTP client; one-writer rule.
- **Why:** makes any future MCP integration auditable and prevents duplicate write authority.
- **Cost/risk:** no new dependency; policy code only.

### B3. Isolated Blender MCP evaluation — **optional, high scrutiny**
- **What:** test `kleer001/blender-mcp` 0.1.0 against Blender 5.2.2 in a throwaway profile with the existing `blender_mcp` addon disabled.
- **Why:** only way to replace an unapproved broad-execution addon with something better understood.
- **Cost/risk:** first real third-party install; must be quarantined, backed up, and reversible.
- **Preconditions:** backup `userpref.blend`; isolated `BLENDER_USER_CONFIG`; no protected `.blend` opened for write; unit + integration evidence.
- **If it fails:** keep current state, record evidence, do not enable either server.

### B4. C++ toolchain — **conditional, low priority**
- **What:** Visual Studio 2022 Build Tools + Windows 10/11 SDK.
- **Why:** only needed to compile C++ Blender addons, Python C extensions, or UE C++ modules.
- **Cost/risk:** multi-GB install on a drive with limited free space; long install time.
- **Decision rule:** skip unless a concrete compile task appears.

### B5. Unreal isolated test project — **deferred**
- **What:** new empty UE 5.8 project with Python/Editor Scripting/Sequencer plugins enabled *in that project only*.
- **Why:** prerequisite for any Unreal automation.
- **Risk:** EXPERIMENTAL Python; several GB of project/DDC data.
- **Precondition:** explicit approval + disk budget (D: has ~110 GB free).

## C. Explicitly NOT in Phase 02
- Redis, Celery, PostgreSQL, Docker, Kubernetes.
- React/Vite/Node build chain.
- Cloud AI generation APIs or asset marketplaces.
- Any Unreal MCP server (license/staleness unresolved).
- Any change to `D:\Projects\01_3D_Blender\Blender Project`.
- Public bind, firewall rule, tunnel, or deployment.

## D. Phase 02 acceptance criteria (proposed)
1. Worker executes an allow-listed no-op/validation job end-to-end with append-only evidence.
2. Invalid transitions and unauthorized paths still fail atomically.
3. No new listener except `127.0.0.1`.
4. Protected hashes unchanged.
5. Full test suite + validator pass; rollback documented and rehearsed.
6. Any third-party install (B3/B4/B5) has license, version, source, hash and uninstall steps recorded.

## E. Rollback posture
- Code: reversible via version control / file removal.
- Database: pre-change backup in `storage/60_BACKUPS/` with integrity check.
- Blender: `userpref.blend` backup restored if MCP evaluation is attempted.
- Unreal: delete the isolated test project only; never touch existing projects.

## F. Owner decisions required before Phase 02
1. Approve **B1 + B2 only**, or include **B3** (Blender MCP test)?
2. Defer **B4** unless a compile need appears? (recommended: defer)
3. Defer **B5** (Unreal test project) to a later phase? (recommended: defer)
