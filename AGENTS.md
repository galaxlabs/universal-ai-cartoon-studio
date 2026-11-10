# universal-ai-cartoon-studio Agent Notes

Project-specific rules belong only in this file. Global workflow is in `E:\agents\AGENTS.md`; durable memory is in `ref/`.

## Scope
- Repository purpose: Local-first production manager and controlled automation layer for reusable 3D cartoon series built with Blender and Unreal Engine.
- Primary stack: Python, FastAPI candidate, SQLAlchemy/Alembic candidate, SQLite, Jinja/HTMX candidate, Blender Python/MCP, Unreal Editor Python and Sequencer.

## Commands
- Phase 0 health check: `py scripts/phase0/health_check.py`
- Phase 0 validation: `py scripts/phase0/validate_foundation.py`
- Setup/build: blocked until Phase 1 dependency approval.

## Project Rules
- The Creative Director is the final approval authority.
- Never modify, move, rename, overwrite, import into, or save over protected Damascus source assets without explicit approval.
- Bind all future local web and MCP services to loopback only unless separately approved.
- Every write-capable Blender or Unreal operation must target a per-job development workspace, never a protected or approved master path.
- Do not enable overlapping Blender MCP servers. Existing external add-ons remain unapproved until backed up and tested.
- Maintain component, capability, job, validation, approval, backup and audit records.
- Major phases stop for approval; destructive, paid, privileged or security-sensitive actions always require explicit approval.
- Large binaries remain in managed storage; SQLite records metadata, hashes, relationships and lifecycle state.
- Keep durable decisions and session results in `ref/`.

## Universal 3D Asset Production
- Shared implementation/production status is in root `PROJECT_STATUS_UR.md`. Local `ref/` notes may not be shipped with a fresh checkout; request missing approved source material rather than inventing it.
- For the user-designated `D:\instruction` sources, consult `ref/instruction-source-review-2026-11-10.md` before related story/asset planning; keep historical archives, proposals, current technical evidence, and explicit approvals distinct. Do not revive old H: output paths or treat reading instructions as phase/asset approval.
- Before story-to-asset extraction, asset library planning, Blender standards, Unreal export planning, or asset production, read `ref/universal-3d-asset-production-foundation.md` and apply the user's standing instructions there.
- Start from the first user-approved story/episode batch; if missing, request its text or approved document paths. Do not treat genre examples or software test fixtures as story canon.
- Produce the eight required planning deliverables and the smallest reusable P0 asset set first. Separate confirmed requirements from proposals; do not invent permanent identities, designs, or environments.
- Do not model, generate asset files, install software, write automation scripts, or render before the relevant specifications are reviewed and explicitly approved. Never overwrite approved source assets.
- For Islamic historical productions: no depiction of Prophets in any form (including silhouettes, reflections, or shadows), no generated voices for them, and no faces of Sahabah or revered women. Distinguish documented history from fictional reconstruction.

