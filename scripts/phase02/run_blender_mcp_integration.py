"""Run the approved Blender MCP test through the Studio argument-aware gateway."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from studio_manager.config import default_settings  # noqa: E402
from studio_manager.contracts import ApprovalCreate  # noqa: E402
from studio_manager.database import create_database_engine, upgrade_database  # noqa: E402
from studio_manager.mcp_gateway import (  # noqa: E402
    MCPGateway,
    MCPGatewayPolicy,
    MCPInvocationRequest,
    approval_subject,
)
from studio_manager.mcp_manager import MCPManager, MCPRegistration  # noqa: E402
from studio_manager.service import StudioService  # noqa: E402

BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
INTEGRATION = ROOT / "storage" / "10_DEVELOPMENT" / "integrations" / "blender"
PROFILE = INTEGRATION / "profile"
WORKSPACE = INTEGRATION / "workspace"
MCP_EXE = INTEGRATION / "runtime" / ".venv" / "Scripts" / "mcp-for-blender.exe"
STARTUP = ROOT / "scripts" / "phase02" / "blender_isolated_startup.py"
REPORT = ROOT / "storage" / "80_REPORTS" / "phase02_blender_mcp_integration.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class MCPStdioClient:
    def __init__(self, command: Path, env: dict[str, str]):
        self.process = subprocess.Popen(  # noqa: S603
            [str(command)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.errors: list[str] = []
        self._next_id = 1
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                self.errors.append(line.rstrip())

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.errors.append(line.rstrip())

    def send(self, method: str, params: dict[str, Any] | None = None, timeout: int = 190) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(1.0, deadline - time.monotonic()))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"MCP process exited {self.process.returncode}: {self.errors[-20:]}"
                    ) from None
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"], sort_keys=True))
                return message.get("result", {})
        raise TimeoutError(f"MCP request timed out: {method}")

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        assert self.process.stdin is not None
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def initialize(self) -> dict[str, Any]:
        result = self.send(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "uacs-phase02", "version": "1.0.0"},
            },
        )
        self.notify("notifications/initialized")
        return result

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.send("tools/call", {"name": tool, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(f"MCP tool failed: {json.dumps(result, sort_keys=True, default=str)}")
        return result

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)


def wait_for_port(port: int, process: subprocess.Popen[str], timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Blender exited before MCP startup: {process.returncode}")
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError("Blender MCP port 9876 did not open")


def scene_code() -> str:
    blend = (WORKSPACE / "Phase02_Blender_MCP_Test.blend").as_posix()
    glb = (WORKSPACE / "Phase02_Blender_MCP_Test.glb").as_posix()
    render = (WORKSPACE / "Phase02_Blender_MCP_Test.png").as_posix()
    return f'''import bpy
from mathutils import Vector
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
cube = bpy.context.object
cube.name = "PH02_TestCube"
cube.scale = (1.5, 1.5, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
mat = bpy.data.materials.new("PH02_BlueMaterial")
mat.diffuse_color = (0.03, 0.18, 0.8, 1.0)
cube.data.materials.append(mat)
bpy.ops.object.camera_add(location=(7, -7, 5), rotation=(1.1, 0, 0.78))
camera = bpy.context.object
camera.name = "PH02_Camera"
bpy.context.scene.camera = camera
direction = cube.location - camera.location
camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
bpy.ops.object.light_add(type="AREA", location=(4, -4, 6))
light = bpy.context.object
light.name = "PH02_KeyLight"
light.data.energy = 1200
light.data.shape = "DISK"
light.data.size = 5
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.object
ground.name = "PH02_Ground"
ground_mat = bpy.data.materials.new("PH02_GroundMaterial")
ground_mat.diffuse_color = (0.12, 0.12, 0.12, 1.0)
ground.data.materials.append(ground_mat)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = r"{render}"
scene.world.color = (0.04, 0.04, 0.04)
bpy.ops.wm.save_as_mainfile(filepath=r"{blend}")
bpy.ops.object.select_all(action="DESELECT")
cube.select_set(True)
bpy.context.view_layer.objects.active = cube
bpy.ops.export_scene.gltf(filepath=r"{glb}", export_format="GLB", use_selection=True)
bpy.ops.render.render(write_still=True)
print("PHASE02_SCENE_CREATED", cube.name, r"{blend}", r"{glb}", r"{render}")'''


def register_gateway(engine) -> tuple[MCPGateway, str, str]:
    manager = MCPManager(engine)
    existing = next((item for item in manager.list_servers() if item["name"] == "blender-mcp-phase02"), None)
    if existing:
        server_id = str(existing["id"])
    else:
        server_id = str(
            manager.register(
                MCPRegistration(
                    name="blender-mcp-phase02",
                    source_url="https://github.com/ahujasid/mcp-for-blender",
                    version="2.2.6@992233bb258975a05eec8b5691465c50c2831e34",
                    license="MIT",
                    bind_host="127.0.0.1",
                    permissions=["read_scene", "write_scene", "render"],
                )
            )["id"]
        )
    gateway = MCPGateway(engine)
    gateway.set_policy(
        server_id,
        MCPGatewayPolicy(
            application="BLENDER",
            operation_selector="tool",
            allowed_operations=["get_addon_status", "get_scene_info", "look", "execute_blender_code"],
            denied_operations=["generate_3d", "import_asset", "search_assets", "search_mentions"],
            write_operations=["execute_blender_code"],
            approval_operations=["execute_blender_code"],
            write_scopes=[str(WORKSPACE)],
            timeout_seconds=240,
            max_concurrency=1,
            retry_limit=0,
            rollback_strategy="delete_phase02_blender_outputs",
            enabled=True,
        ),
    )
    subject = approval_subject(server_id, "execute_blender_code")
    service = StudioService(engine)
    with engine.connect() as connection:
        existing_approval = connection.execute(
            __import__("sqlalchemy").text(
                "SELECT id FROM approvals WHERE subject_kind='MCP_OPERATION' AND subject_id=:subject "
                "AND decision='APPROVED' ORDER BY created_at DESC LIMIT 1"
            ),
            {"subject": subject},
        ).first()
    approval_id = (
        str(existing_approval[0])
        if existing_approval
        else str(
            service.create_approval(
                ApprovalCreate(
                    subject_kind="MCP_OPERATION",
                    subject_id=subject,
                    decision="APPROVED",
                    decided_by="creative-director",
                    notes="Approved revised Phase 02 isolated Blender MCP integration test",
                    evidence={"workspace": str(WORKSPACE), "safe_mode": True},
                )
            )["id"]
        )
    )
    return gateway, server_id, approval_id


def main() -> int:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for name in ("Phase02_Blender_MCP_Test.blend", "Phase02_Blender_MCP_Test.glb", "Phase02_Blender_MCP_Test.png"):
        (WORKSPACE / name).unlink(missing_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "BLENDER_USER_CONFIG": str(PROFILE / "config"),
            "BLENDER_USER_SCRIPTS": str(PROFILE / "scripts"),
            "BLENDER_MCP_SAFE_MODE": "1",
            "BLENDER_HOST": "127.0.0.1",
            "BLENDER_PORT": "9876",
            "DO_NOT_TRACK": "1",
        }
    )
    blender = subprocess.Popen(  # noqa: S603
        [str(BLENDER), "--factory-startup", "--python", str(STARTUP)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    client: MCPStdioClient | None = None
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_02_BLENDER_MCP_INTEGRATION",
        "blender_pid": blender.pid,
        "safe_mode": True,
        "workspace": str(WORKSPACE),
    }
    try:
        wait_for_port(9876, blender)
        client = MCPStdioClient(MCP_EXE, env)
        report["initialize"] = client.initialize()
        tools = client.send("tools/list").get("tools", [])
        report["tools"] = sorted(tool["name"] for tool in tools)
        settings = default_settings()
        upgrade_database(settings.database_path)
        engine = create_database_engine(settings.database_path)
        gateway, server_id, approval_id = register_gateway(engine)

        before = gateway.execute(
            server_id,
            MCPInvocationRequest(tool_name="get_scene_info", arguments={"user_prompt": "Phase 02 isolated test"}),
            lambda: client.call("get_scene_info", {"user_prompt": "Phase 02 isolated test"}),
        )
        code = scene_code()

        def rollback() -> None:
            for name in (
                "Phase02_Blender_MCP_Test.blend",
                "Phase02_Blender_MCP_Test.glb",
                "Phase02_Blender_MCP_Test.png",
            ):
                (WORKSPACE / name).unlink(missing_ok=True)

        written = gateway.execute(
            server_id,
            MCPInvocationRequest(
                tool_name="execute_blender_code",
                arguments={"code": code, "user_prompt": "Create the approved Phase 02 isolated Blender scene"},
                workspace_path=str(WORKSPACE),
                approval_id=approval_id,
                actor="phase02-integration",
            ),
            lambda: client.call(
                "execute_blender_code",
                {"code": code, "user_prompt": "Create the approved Phase 02 isolated Blender scene"},
            ),
            rollback,
        )
        after = gateway.execute(
            server_id,
            MCPInvocationRequest(tool_name="get_scene_info", arguments={"user_prompt": "Verify Phase 02 scene"}),
            lambda: client.call("get_scene_info", {"user_prompt": "Verify Phase 02 scene"}),
        )
        outputs = []
        for name in ("Phase02_Blender_MCP_Test.blend", "Phase02_Blender_MCP_Test.glb", "Phase02_Blender_MCP_Test.png"):
            path = WORKSPACE / name
            exists = path.is_file()
            outputs.append({
                "path": str(path),
                "exists": exists,
                "bytes": path.stat().st_size if exists else 0,
                "sha256": sha256(path) if exists else None,
            })
        report.update(
            {
                "status": "PASS" if all(item["exists"] and item["bytes"] > 0 for item in outputs) else "FAIL",
                "server_id": server_id,
                "approval_id": approval_id,
                "before_invocation": before["invocation_id"],
                "write_invocation": written["invocation_id"],
                "after_invocation": after["invocation_id"],
                "outputs": outputs,
                "gateway_invocations": gateway.list_invocations(server_id),
                "mcp_stderr_tail": client.errors[-30:],
            }
        )
        engine.dispose()
    except Exception as exc:
        report.update({"status": "FAIL", "error": type(exc).__name__, "message": str(exc)})
    finally:
        if client:
            client.close()
        blender.terminate()
        try:
            blender.wait(timeout=15)
        except subprocess.TimeoutExpired:
            blender.kill()
            blender.wait(timeout=10)
        if blender.stdout:
            report["blender_stdout_tail"] = blender.stdout.read().splitlines()[-50:]
        report["blender_exit_code"] = blender.returncode
        REPORT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(REPORT)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
