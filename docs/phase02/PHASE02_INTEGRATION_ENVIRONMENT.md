# Phase 02 Integration Environment

## Blender

- Blender: 5.2.2 LTS.
- Isolated root: `storage/10_DEVELOPMENT/integrations/blender`.
- Profile, source, runtime, and workspace are separated from the user's global Blender profile.
- MCP listener: `127.0.0.1:9876`; safe mode on; telemetry off.

## Unreal

- Unreal Engine: 5.8.4, build `58902052`.
- Blueprint-only project: `storage/10_DEVELOPMENT/integrations/unreal/Phase02_UE_MCP_Test`.
- PinWright listener: `127.0.0.1:25364` with bearer token published inside the isolated project.
- The harness launches Unreal detached without `-log`/`-stdout`, because those console flags caused reproducible `ConsoleCtrl` exits in this automation host. Readiness is measured from the project log.

## Boundaries

- Writes: managed integration project/workspace only.
- Protected production root: read-only and never opened by either integration harness.
- Promotion: not performed.
- Public binding, deployment, service installation, firewall changes, and C++ toolchain installation: not performed.
