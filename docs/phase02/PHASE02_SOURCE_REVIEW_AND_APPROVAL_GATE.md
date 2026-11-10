# Phase 02 Source Review and Approval Gate

Date: 2026-10-30
Status: BLOCKED pending revised Creative Director approval
Review mode: source-only; no installer or third-party code executed

## Scope discrepancy

The approved Phase 01 plan permits B1+B2 only. It labels Blender MCP evaluation optional, defers the isolated Unreal project, and explicitly excludes every Unreal MCP from Phase 02. The newer Phase 02 objective requires working Blender and Unreal MCP integrations. That is a material scope change and cannot be inferred from the older approval.

## Candidate evidence

### Blender MCP — conditional selection

**Repository:** `ahujasid/mcp-for-blender`

- Reviewed commit: `992233bb258975a05eec8b5691465c50c2831e34`
- Package version: `2.2.6`
- License: MIT (`LICENSE` and `pyproject.toml` agree)
- Python: `>=3.10`
- Dependencies: `mcp>=1.26.0,<2`, `httpx>=0.27.0`
- Transport: MCP over stdio; Blender add-on TCP bridge defaults to `localhost:9876`
- MCP surface: 14 tools, including `execute_blender_code`
- Risk: the add-on ultimately calls Python `exec()` inside Blender. The upstream opt-in `BLENDER_MCP_SAFE_MODE=1` validator blocks `eval`, `exec`, `open`, `os`, subprocess, network, handlers/timers and external `.blend` loading, but still allows render, save and import/export operators.
- External features: Poly Haven, Sketchfab, Poly Pizza and paid/credentialed 3D generators are present. They must remain disabled for local integration tests.
- Existing user add-on is an older same-upstream build (addon 1.8/protocol 13), not the reviewed 2.2.6 source. It must not be upgraded in-place for evaluation.

**Decision:** eligible only for an isolated Blender profile, pinned to the reviewed commit, with safe mode forced on, telemetry not consented, external providers disabled, protected paths denied, and every write routed through the Studio gateway. No direct global MCP-client registration.

### Blender Orchestrator — reject

**Repository:** `mlolson/blender-orchestrator`

- Reviewed commit: `a9dfb32d41709dd013b3c6ca0802bb869040656d`
- Package version: `0.1.0`
- Repository API license: absent; no root `LICENSE` file. README license language is not sufficient for installation approval.
- MCP surface: 101 tools with broad scene-write capability.
- Blender HTTP bridge defaults to `localhost:8765`, which conflicts with the Studio Manager at `127.0.0.1:8765`.
- The bridge has no authentication and returns `Access-Control-Allow-Origin: *`.
- It overlaps the selected Blender MCP's write authority.

**Decision:** reject and keep disabled. Spatial ideas may be reimplemented later as Studio-owned allow-listed adapters; do not execute this repository.

### Unreal MCP — primary conditional selection

**Repository:** `PinWright/pinwright-ue`

- Reviewed head: `5bc052c2b4b84b935cd9eef5645d1d92799d111a` (source version 1.1.0, unreleased at review time)
- Installable release: `v1.0.0`, tag commit `20de4b5d6f18e9839aca17cc732fd6ef0a54a260`
- License: MIT
- Exact UE 5.8 Win64 prebuilt: `PinWright-1.0.0-UE5.8-Win64.zip`
- Release digest: `sha256:80259ddf99083e36bfda2a062a603e797ec5e54b3797c3131a7e7ad858be6376`
- Transport: loopback-only HTTP endpoint with bearer-token authentication required by default; a zero-dependency stdio proxy reads project-local token and port files.
- Port: project-derived `19880`–`30119` by default.
- Compatibility: a UE 5.8-specific prebuilt package exists, so a Blueprint-only isolated project should not require the absent MSVC/Windows SDK toolchain.
- Risk: MCP advertises one generic `call` tool and places the real RPC operation in `method`; `python.execute` provides arbitrary Unreal Python. A policy that checks only the MCP tool name cannot secure it.
- Scope: very broad project-authoring surface and many optional engine-plugin dependencies.

**Decision:** preferred Unreal candidate only if the Studio gateway inspects and authorizes nested `method` values, denies `python.execute` and process/build controls by default, limits writes to the isolated project, and records before/after evidence. Use release `v1.0.0`, not unreleased head.

### Unreal MCP — reject as primary

**Repository:** `GenOrca/unreal-mcp`

- Reviewed commit: `f7986db239516aa4299ddc6f54d713253bd82631`
- Release: `v2.2.0`, tag commit `2ca650f75eef71d5f245024c3e39173760f9ee49`
- License: Apache-2.0
- Exact UE 5.8 Win64 prebuilt: `UnrealMCPython_5.8_2.2.0.zip`
- Release digest: `sha256:b7431e7fe6b4f54417508ce012c551c71ccf9c2a058d47b7ef4761f6ba6d59b8`
- Transport: stdio MCP dispatcher to an unauthenticated fixed TCP bridge on `127.0.0.1:12029`.
- Surface: 253 actions across 21 domains plus arbitrary `execute_python`; actions are nested under generic dispatcher tools such as `util`.

**Decision:** do not install as the primary server. It has an exact UE 5.8 build but weaker local authentication and another nested arbitrary-code escape hatch. Keeping both Unreal servers would duplicate write authority.

### Blender skills — conditional subset

**Repository:** `EL4CTEO/blender-skills`

- Reviewed commit: `71d031dab8bc6729504d11a78cbe91945401045f`
- License: MIT
- Repository contains 22 Blender 5.2-oriented skills.
- Installer can recursively remove and replace destination skill folders. Do not run it.
- Proposed project-scoped, copy-only subset:
  - `blender-core`
  - `blender-scene-setup`
  - `blender-pbr-materials`
  - `blender-lighting-lookdev`
  - `blender-animation`
  - `blender-rendering`
  - `blender-export-pipelines`
  - `blender-asset-qa`

**Decision:** eligible after approval by copying only reviewed folders into a project-controlled skills area. Do not install all 22 globally and do not run the upstream installer.

## Current gateway gap

`src/studio_manager/mcp_manager.py` is a disabled metadata registry and activation-policy preview, not a gateway or MCP client. It currently:

- stores only coarse permissions (`read_scene`, `write_scene`, `render`, `execute_code`);
- exposes no activation path;
- does not proxy calls;
- does not inspect nested arguments such as PinWright `call(method="python.execute")` or GenOrca `util(action="execute_python")`;
- has no per-operation approval, path policy, concurrency control, timeout/retry execution, rollback hook or invocation evidence;
- blocks any registration declaring `execute_code`, rather than permitting a reviewed server while denying its unsafe operation.

Therefore neither selected MCP may be activated safely until an argument-aware Studio gateway and tests exist.

## Proposed bounded implementation after approval

1. Extend the registry with pinned source/release hashes, transport, executable/plugin path, capability rules and rollback metadata.
2. Implement an argument-aware loopback gateway before activating either integration.
3. Deny arbitrary Python, shell/process, build, global save, external network/provider and out-of-scope path operations by default.
4. Create an isolated Blender profile under managed development storage; preserve the existing user profile and add-on unchanged.
5. Install the reviewed Blender MCP only into that isolated profile and force safe mode.
6. Create a Blueprint-only UE 5.8 test project under managed development storage.
7. Install the exact PinWright UE 5.8 release asset into that test project only; verify its published SHA-256 before extraction.
8. Copy only the approved Blender skill subset; create Studio-owned `SK-001`–`SK-006` separately.
9. Run staged health, scene-authoring, export/import, Sequencer/render and rollback tests without opening protected assets.
10. Publish the requested eleven Phase 02 records and stop before Phase 03.

## Approval required

The Creative Director must explicitly approve or amend all of the following as one revised Phase 02 gate:

1. Evaluate `ahujasid/mcp-for-blender` 2.2.6 at commit `992233bb...` in an isolated Blender profile.
2. Install PinWright `v1.0.0` UE 5.8 prebuilt, digest `80259ddf...`, in a new Blueprint-only isolated UE project.
3. Build the argument-aware Studio MCP gateway before activating either server.
4. Copy only the eight listed Blender skills at commit `71d031da...`; do not run the upstream installer.
5. Reject/disable Blender Orchestrator and GenOrca Unreal MCP.
6. Keep the C++ toolchain deferred unless the verified prebuilt package fails for a compile-specific reason.
7. Permit creation of isolated test data only under managed development/temp storage; protected project roots remain read-only and untouched.

Until this gate is approved, the integration phase remains **BLOCKED** and no installation or activation will occur.

## Gate resolution — 2026-10-30

The Creative Director approved all seven items above. Implementation remained confined to managed integration storage. Blender Orchestrator and GenOrca were not installed, the C++ toolchain remained deferred, and protected production assets remained read-only.
