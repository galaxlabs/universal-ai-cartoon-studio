# SYSTEM INVENTORY — Phase 01

Recorded: 2026-10-30 (Asia/Karachi, +05:00)
Method: read-only OS/registry/executable queries. No application settings changed.

## 1. Machine
| Item | Value |
|---|---|
| OS | Microsoft Windows 10 Pro, build 19045 (22H2) |
| Model | Lenovo 20HKCTO1WW (ThinkPad P71 class) |
| CPU | Intel Xeon E3-1505M v6 @ 3.00 GHz — 4 cores / 8 logical |
| RAM | 15.57 GB usable (~16 GB installed) |
| GPU (discrete) | NVIDIA Quadro P3000, 6144 MiB, driver 573.22, compute capability 6.1 |
| GPU (integrated) | Intel HD Graphics P630 |

## 2. Storage (free / total, GB)
| Drive | Free | Total |
|---|---|---|
| C: | 76.91 | 271.51 |
| D: | 110.00 | 112.30 |
| E: | 27.43 | 112.30 |
| F: | 107.11 | 112.30 |
| G: | 70.04 | 112.30 |
| H: | 107.19 | 112.30 |
| I: | 63.74 | 97.91 |

Note: C: free space is materially higher than the 10.2 GB recorded during the earlier Phase 0. This value is reported as measured now, not explained by this phase.
Project and managed storage live on D:. Temporary/generated work must not target C:.

## 3. Python installations
| Runtime | Version | Path | Role |
|---|---|---|---|
| System Python | 3.14.4 | `C:\Python314\python.exe` | discovery/utility only |
| uv-managed CPython | 3.13.13 | `D:\...\Universal_AI_Cartoon_Studio\.python\cpython-3.13.13-...` | **selected application runtime** |
| Blender embedded | 3.13.13 | `C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe` | Blender-only, never for the web app |
| Unreal embedded | 3.11.x (`python_v3.11.x.tps`) | `C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\ThirdParty\Python3\Win64` | Unreal editor-only |

The uv-managed 3.13.13 is intentionally not registered with the `py` launcher; `py -0p` shows only 3.14.4. This is expected.

## 4. Toolchain availability
| Tool | Status | Version / note |
|---|---|---|
| Git | PRESENT | 2.54.0.windows.1 |
| Git LFS | PRESENT | git-lfs/3.7.1 |
| Node.js | PRESENT | v24.16.0 |
| npm | PRESENT | 11.13.0 |
| Corepack / pnpm / yarn shims | PRESENT (shims only) | `C:\nvm4w\nodejs\*.ps1`; pnpm version **unverified** — intentionally not invoked (previous probe triggered an unrequested Corepack download) |
| uv | PRESENT | 0.11.8 |
| FFmpeg | PRESENT | 8.1.1 full build |
| C/C++ compiler (`cl`, `clang`, `gcc`) | **ABSENT** | not on PATH |
| CMake / Ninja / MSBuild | **ABSENT** | not on PATH |
| Visual Studio 2022 / Build Tools | **ABSENT** | `C:\Program Files\Microsoft Visual Studio\2022` exists but contains no components; `vswhere` reports no instances |
| Windows SDK headers | **ABSENT** | `C:\Program Files (x86)\Windows Kits\10\Include` not present |

Impact: no native-module compilation (Blender C++ addons, UE C++ projects, Python C extensions). Pure-Python pipeline is unaffected.

## 5. Network / local-service posture
- Windows Firewall enabled on Domain, Private, and Public profiles; inbound/outbound defaults report `NotConfigured` (OS defaults effectively apply).
- Studio policy: `bind_host = 127.0.0.1`, `allow_public_bind = false`.
- Current Studio service listens only on `127.0.0.1:8765` (verified).
- No port-forwarding, tunnel, or public endpoint detected or created by this phase.

## 6. Existing project workspace
| Item | Value |
|---|---|
| Canonical root | `D:\Projects\06_Studio_Systems\Universal_AI_Cartoon_Studio` |
| Compatibility junction | `E:\Projects\universal-ai-cartoon-studio` |
| Protected production root | `D:\Projects\01_3D_Blender\Blender Project` |
| Managed storage zones | `00_PROTECTED_SOURCES`, `10_DEVELOPMENT`, `20_TEMP`, `30_VALIDATED`, `40_APPROVED_MASTERS`, `50_PUBLISHED_OUTPUTS`, `60_BACKUPS`, `70_LOGS`, `80_REPORTS`, `90_QUARANTINE` |
| Database | `storage/30_DATABASES/studio.db` (SQLite, WAL) |

Layout note: both `storage/30_VALIDATED` (declared zone) and `storage/30_DATABASES` (database location) exist. This is a naming overlap to reconcile in a later approved cleanup; it is not a defect affecting data integrity.

## 7. Verification
`scripts/phase0/health_check.py` → **PASS**, including protected-source SHA-256 equality for V004, V006 and Atlas V10.
