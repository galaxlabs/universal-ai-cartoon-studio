# ADR-0002 — Blender and Unreal automation boundaries

Status: Proposed for Phase 1 approval

## Decision
- Use versioned CLI scripts for deterministic Blender operations.
- Evaluate exactly one Blender MCP server in an isolated test profile; do not enable duplicate write-capable servers.
- Use Unreal's built-in editor Python and scripting plugins in a new isolated project.
- Expose only capability-specific operations through the Studio Manager. Raw `exec`/`eval` stays disabled unless a named job receives explicit approval.

## Reason
Both discovered Blender MCP implementations can execute arbitrary Python, and the installed addon also includes optional network asset integrations. Unreal Python is explicitly experimental and editor-only. Capability allowlists, loopback binding, job workspaces and approval gates reduce corruption and exposure risk.
