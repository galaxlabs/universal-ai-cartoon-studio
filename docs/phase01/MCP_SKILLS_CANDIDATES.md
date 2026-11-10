# MCP & SKILLS CANDIDATES — Phase 01

Repository metadata verified via GitHub API on 2026-10-30. Capability claims below are separated from verified facts.

## 1. MCP servers currently configured on this machine
| Client | Config file | Configured servers |
|---|---|---|
| Cursor | `~/.cursor/mcp.json` | `blender` |
| VS Code | `%APPDATA%\Code\User\mcp.json` | `blender`, `io.github.github/github-mcp-server`, `io.github.vercel/next-devtools-mcp` |
| Codex | `~/.codex/config.toml` | `blender` (+ tools: `execute_blender_code`, `get_addon_status`, `get_scene_info`, `look`), `node_repl`, `solo` |
| OpenCode | `~/.config/opencode/opencode.json` | `codegraph` |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | absent |

Only server **names** were extracted. No credentials, tokens, or environment values were read or copied.

## 2. Blender MCP candidates
| Candidate | Verified facts | Risk | Verdict |
|---|---|---|---|
| `ahujasid/blender-mcp` (installed addon 1.8, protocol 13) | 32,811 stars; MIT; last push 2026-10-29; 59 open issues | Exposes arbitrary Blender Python execution and optional external asset APIs | **Installed but NOT Studio-approved.** Leave as-is in Phase 01. |
| `kleer001/blender-mcp` 0.1.0 (`12feeb50…`, local at `D:\Projects\05_Tools\blender-mcp`) | 2 stars; MIT; last push 2026-06-04; 0 open issues; claims 175 typed tools across 25 domains; upstream integration-tested on Blender 4.2 LTS | Very small project; **not tested on Blender 5.2.2**; still ships `execute_python` / `evaluate_expression` | **CANDIDATE — isolated test required.** Not installed or enabled. |

Policy: exactly **one** write-capable Blender MCP may be active. Enabling the candidate requires disabling the existing addon in a backed-up, isolated profile.

## 3. Unreal MCP candidates
| Candidate | Verified facts | Risk | Verdict |
|---|---|---|---|
| `chongdashu/unreal-mcp` | 2,110 stars; **no license declared (SPDX null)**; last push 2025-04-22; 41 open issues | Unlicensed redistribution risk; ~18 months behind UE 5.8; no local test | **REJECTED for now** — licensing + staleness + unverified UE 5.8 compatibility |

No Unreal MCP server is installed or enabled.

## 4. Agent Skills / automation candidates
| Area | Candidate approach | Status |
|---|---|---|
| Blender deterministic automation | Versioned `blender --background --python` scripts executed by the Studio worker | **PREFERRED** — testable, auditable, no third-party runtime |
| Blender interactive automation | One approved MCP implementation, loopback only | Deferred to Phase 1C/02 approval |
| Unreal automation | Built-in Python + Editor Scripting + Sequencer Scripting in an isolated project | **PREFERRED**, EXPERIMENTAL; deferred |
| Agent skill packaging | Local `SKILL.md` + scripts under the project | Deferred until a skill is approved and tested |
| Spatial reasoning | Blender `bpy` mathutils / BVHTree / ray_cast; deterministic geometry checks | **STABLE primitives**, tooling to be built |
| Rigging/animation automation | Blender Rigify (present), Unreal Control Rig (present) | Present, unautomated |
| Character pipelines | Manual/scripted first; AI generation unverified | **UNVERIFIED** — no vendor claims accepted |

## 5. Explicit non-candidates
- Redis / Celery / PostgreSQL / Docker: rejected for the current single-user local workload.
- Cloud AI generation APIs: not evaluated, not installed; require cost, privacy and provenance review.
- Quixel Bridge / Fab content plugins: installed upstream but not selected; each asset needs separate licensing review.

## 6. Phase 01 installation actions
**None.** No MCP server, Blender addon, Unreal plugin, or AI skill was installed, enabled, disabled, or reconfigured in this phase.
