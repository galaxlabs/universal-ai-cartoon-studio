# Phase 02 Recovery and Rollback

## Recovery evidence

- Pre-integration database and Blender preference backups are in `storage/60_BACKUPS/phase02_integration/20261030-233749`.
- The Unreal harness deletes only disposable `Content/Phase02` and `Saved/Screenshots/OpenLevel` paths after proving they resolve inside the isolated project, then recreates all outputs.
- A second full Unreal run exercised that reset and recreated the map, imported assets, sequence, and screenshot successfully.
- Temporary validator databases/workspaces are recreated and removed by their validators.

## Stop conditions

- No Blender MCP, PinWright editor, worker, or public service is left running by the test harnesses.
- Preserve `mcp_invocations`, `audit_events`, and approvals as evidence; do not delete them during normal rollback.

## External rollback

1. Remove only `storage/10_DEVELOPMENT/integrations/blender` to discard the isolated Blender profile, source checkout, and test outputs.
2. Remove only `storage/10_DEVELOPMENT/integrations/unreal/Phase02_UE_MCP_Test` to discard the isolated Unreal project and PinWright plugin.
3. Remove the 14 project-local Phase 02 skill folders and `config/phase02.skills.json` if skill rollback is approved.
4. Restore `storage/30_DATABASES/studio.db` from the recorded pre-integration backup only with explicit approval, because doing so removes later audit evidence.

## Source/schema rollback

- Revert `migrations/versions/0003_mcp_gateway.py`, gateway API wiring, `src/studio_manager/mcp_gateway.py`, gateway tests, and Phase 02 integration scripts together.
- Downgrade migration `0003_mcp_gateway` only after exporting audit evidence and receiving explicit approval.
- Do not revert unrelated CSP or HTML-pattern fixes.

## Protected assets

No protected asset restoration is required because their hashes remained unchanged.
