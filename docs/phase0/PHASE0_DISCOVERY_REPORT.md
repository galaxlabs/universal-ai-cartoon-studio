# Phase 0 Discovery Report

## Machine
- Windows 10 Pro 22H2 build 19045, Lenovo 20HKCTO1WW.
- Intel Xeon E3-1505M v6, 4 cores / 8 threads.
- Approximately 16 GB RAM.
- NVIDIA Quadro P3000, driver 573.22, 6 GB VRAM, compute capability 6.1.
- D: has approximately 110 GiB free and is the selected project/storage volume.
- C: has approximately 10.2 GiB free; avoid project environments, caches and render output there.

## Installed applications and runtimes
- Blender 5.2.2 LTS at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`; embedded Python 3.13.13.
- Unreal Engine 5.8.4 at `C:\Program Files\Epic Games\UE_5.8`; embedded editor Python documented as 3.11.8.
- System Python 3.14.4, Node 24.16.0, npm 11.13.0, Git 2.54.0, FFmpeg 8.1.1 and uv 0.11.8.
- Python SQLite runtime 3.50.4, serialized thread-safety mode. Standalone `sqlite3` CLI is absent and not required.

## Blender integrations
- The normal Blender user profile enables `blender_mcp` addon version 1.8 from `ahujasid/mcp-for-blender`.
- It listens on localhost by default but exposes arbitrary `execute_code` and optional external asset integrations. It is existing software, not Studio-approved.
- A second local repository, `kleer001/blender-mcp` 0.1.0 commit `12feeb50b49cd5e8a3152b5f9ea71fb3b4558b1d`, provides 175 typed tools and is MIT licensed. Upstream integration tests target Blender 4.2.5, not local 5.2.2.
- Duplicate write-capable MCP servers are prohibited. Phase 1 must back up preferences, choose one candidate, disable the other for the isolated test profile, and run unit/integration tests.

## Unreal integrations
- Built-in Control Rig and Interchange are enabled by default in descriptors.
- Python Editor Script Plugin and Editor Scripting Utilities are disabled by default, beta/experimental and project-specific.
- Sequencer Scripting depends on Python and is beta.
- Quixel Bridge and Fab plugins are installed but not selected for the core pipeline because each downloaded asset requires separate licensing/provenance review.

## Architecture outcome
- Local modular monolith with FastAPI, server-rendered Jinja/HTMX, SQLAlchemy/Alembic and SQLite.
- One durable local worker; no Redis/Celery/PostgreSQL initially.
- Managed D-drive binary storage and SHA-256 metadata.
- Blender background CLI for deterministic jobs; one controlled MCP candidate for interactive work.
- Unreal built-in scripting in an isolated test project.
- All services loopback-only and all promotions approval-gated.

## Changes in this phase
- Created only the isolated Studio project, documentation, manifests, schema, storage zones and read-only health/validation scripts.
- No Blender preference, Unreal project, firewall, security control or protected production asset was modified.
- No studio dependency was installed. A `pnpm --version` discovery command caused Corepack to download pnpm 12.16.1 into its existing cache; this was unprivileged, created no project setup and is recorded in the component manifest.
