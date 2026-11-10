# Phase 02 Skill Registry

Canonical machine registry: `config/phase02.skills.json`.

## Reviewed third-party subset

Eight MIT-licensed folders were copied project-locally from `EL4CTEO/blender-skills` commit `71d031dab8bc6729504d11a78cbe91945401045f`:

- `blender-core`
- `blender-scene-setup`
- `blender-pbr-materials`
- `blender-lighting-lookdev`
- `blender-animation`
- `blender-rendering`
- `blender-export-pipelines`
- `blender-asset-qa`

The upstream installer was not run and the remaining upstream skills were not copied.

## Studio-owned skills

- `SK-001` managed Blender scene
- `SK-002` Blender quality gate
- `SK-003` Blender-to-Unreal export
- `SK-004` managed Unreal import
- `SK-005` Unreal cinematic test
- `SK-006` integration recovery

All 14 skills are project-local and disabled by default. Tree hashes and file counts are recorded in the JSON registry.
