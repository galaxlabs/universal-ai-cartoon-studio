# Phase 02 Addon and Plugin Registry

## Blender addon

- Component: MCP for Blender 2.2.6.
- Source commit: `992233bb258975a05eec8b5691465c50c2831e34`.
- Location: `storage/10_DEVELOPMENT/integrations/blender/profile` and project-local runtime/source paths.
- Mode: isolated Blender 5.2 profile, safe mode enabled, telemetry disabled, loopback only.
- Result: PASS.
- Global Blender profile: not installed over or modified; `userpref.blend` post-run hash equals baseline.

The server's internal MCP metadata reports version `1.30.0`; the installed package/repository pin remains 2.2.6. The server warning about the global addon path is advisory and does not change the isolated-profile evidence.

## Unreal plugin

- Component: PinWright 1.0.0 UE 5.8 prebuilt.
- Source commit: `20de4b5d6f18e9839aca17cc732fd6ef0a54a260`.
- Archive SHA-256: `80259ddf99083e36bfda2a062a603e797ec5e54b3797c3131a7e7ad858be6376`.
- Location: isolated project `Plugins/PinWright` only.
- Result: loaded successfully in Unreal Engine 5.8.4; no C++ compilation required.

## Exclusions

Blender Orchestrator, GenOrca, global addon installation, and production-project plugin installation were not performed.
