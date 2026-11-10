# SOFTWARE COMPATIBILITY MATRIX — Phase 01

Legend: **STABLE** = verified working on this machine · **EXPERIMENTAL** = vendor-labelled beta/experimental · **UNVERIFIED** = advertised/upstream-only, not tested here · **BLOCKED** = incompatible with current policy or toolchain.

## 1. Host applications
| Software | Version | Status here | Evidence |
|---|---|---|---|
| Blender | 5.2.2 LTS (build 2026-09-15, hash `d13f752e3b9c`) | STABLE | `blender --version`; background startup verified earlier |
| Blender embedded Python | 3.13.13 | STABLE | `python.exe --version` |
| Unreal Engine | 5.8.4, changelist 58902052 (compatible 55116800) | STABLE (engine only) | `Engine/Build/Build.version` |
| Unreal embedded Python | 3.11.x (`python_v3.11.x.tps`) | EXPERIMENTAL | plugin is under `Engine/Plugins/Experimental` |
| Windows 10 Pro 19045 | — | STABLE | OS query |
| Quadro P3000 / 6 GB / CC 6.1 | driver 573.22 | FUNCTIONAL | `nvidia-smi`; 6 GB VRAM constrains large-scene rendering |

## 2. Unreal plugins (bundled, verified descriptors present)
| Plugin | Descriptor path | Vendor status |
|---|---|---|
| PythonScriptPlugin | `Engine/Plugins/Experimental/PythonScriptPlugin` | EXPERIMENTAL |
| EditorScriptingUtilities | `Engine/Plugins/Editor/EditorScriptingUtilities` | EDITOR (disabled by default per descriptor) |
| SequencerScripting | `Engine/Plugins/MovieScene/SequencerScripting` | BETA |
| ControlRig | `Engine/Plugins/Animation/ControlRig` | STABLE (enabled by default) |
| Interchange | `Engine/Plugins/Interchange/Runtime` | STABLE (enabled by default) |

Unreal Python/editor automation on 5.8.4 remains **UNVERIFIED** locally: no isolated UE project has been created or launched.

## 3. Web/database stack (installed and tested)
| Component | Version | License | Status |
|---|---|---|---|
| CPython | 3.13.13 (uv-managed, project-local) | PSF | STABLE |
| FastAPI | 0.162.0 | MIT | STABLE — 14 tests pass |
| Uvicorn | 0.54.0 | BSD-3-Clause | STABLE — real process smoke test pass |
| Jinja | 3.1.6 | BSD-3-Clause | STABLE |
| SQLAlchemy | 2.1.6 | MIT | STABLE |
| Alembic | 1.20.1 | MIT | STABLE — upgrade/downgrade/re-upgrade pass |
| SQLite (stdlib) | 3.50.4 | Public domain | STABLE — WAL, FK, FULL sync, backup/restore pass |
| HTMX | 2.0.11 (commit `fa978b24`) | 0BSD | STABLE — vendored, SHA-256 verified, served locally |
| python-multipart | 0.0.32 | Apache-2.0 | STABLE |

## 4. Frontend options
| Option | Status | Assessment |
|---|---|---|
| Jinja + locally vendored HTMX | STABLE (deployed) | Simplest; no build step; CSP-compatible after `style-src 'unsafe-inline'` |
| React / Vite SPA | UNVERIFIED, **not adopted** | Adds Node build chain, bundler supply chain, and a second CSP surface for a single-user local tool |

## 5. Media / rendering
| Capability | Status |
|---|---|
| FFmpeg 8.1.1 (x264/x265/AV1/NVENC/DXVA) | STABLE |
| Blender Cycles/Eevee CLI render | STABLE (engine present); GPU Cycles unmeasured on 6 GB VRAM |
| Unreal Sequencer render | UNVERIFIED (no test project) |

## 6. Known compatibility risks
1. **No C++ toolchain** — blocks compiling Blender C++ addons, Python C extensions, and UE C++ source builds. Blender/UE *binary* installs are unaffected.
2. **Only 6 GB VRAM** — limits high-resolution Cycles/UE scenes; render budgets must be explicit.
3. **Unreal Python is beta/experimental on 5.8** — every automation needs an isolated project test before production use.
4. **Two Blender MCP implementations** exist in the environment (installed addon + local repo). Running both would create duplicate write authority.
5. **Unreal MCP ecosystem is immature** — see `MCP_SKILLS_CANDIDATES.md`; one popular candidate has no declared license and is stale against UE 5.8.
6. **Node package-manager shims** exist via Corepack; versions are unverified and no Node project is required by the adopted architecture.
