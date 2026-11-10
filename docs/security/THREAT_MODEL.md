# Phase 0 Threat Model

## Protected assets
- Original Damascus/Atlas/TILISM files.
- Approved character masters, rigs, scenes and published renders.
- SQLite approvals, audit events and component registry.
- Credentials for optional external services.

## Primary risks
- Arbitrary Python execution through Blender MCP or Unreal scripting.
- Path traversal or a job writing into protected/master directories.
- Duplicate MCP servers with overlapping write authority.
- Publicly reachable local services.
- Unlicensed downloaded assets or unclear provenance.
- A failed job partially overwriting an approved file.
- SQLite/database and binary-store versions drifting apart.

## Mandatory controls
- Loopback binding and Windows firewall unchanged.
- Canonical-path allowlist and deny-by-default protected roots.
- Per-job workspace, output hash and atomic promotion after validation/approval.
- No in-place edits to protected or approved files.
- MCP capabilities disabled until installation and integration tests pass.
- Secrets stored outside source and logs; never committed.
- Append-only audit events for approvals and promotions.
- Database backup plus output manifest before migration or promotion.
