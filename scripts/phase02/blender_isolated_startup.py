"""Enable the reviewed Blender MCP addon inside the isolated Phase 02 profile."""

from __future__ import annotations

import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / "storage" / "10_DEVELOPMENT" / "integrations" / "blender" / "workspace" / "startup.json"


def main() -> None:
    bpy.ops.preferences.addon_enable(module="blender_mcp")
    addon = bpy.context.preferences.addons.get("blender_mcp")
    if addon and hasattr(addon.preferences, "telemetry_consent"):
        addon.preferences.telemetry_consent = False
    bpy.ops.wm.save_userpref()
    result = bpy.ops.blendermcp.start_server()
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(
        json.dumps(
            {
                "addon_enabled": "blender_mcp" in bpy.context.preferences.addons,
                "operator_result": sorted(result),
                "blender_version": bpy.app.version_string,
                "background": bpy.app.background,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


main()
