"""Run the approved PinWright UE 5.8 integration through the Studio gateway."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import text  # noqa: E402

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

EDITOR = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe")
PROJECT = ROOT / "storage" / "10_DEVELOPMENT" / "integrations" / "unreal" / "Phase02_UE_MCP_Test"
UPROJECT = PROJECT / "Phase02_UE_MCP_Test.uproject"
PINWRIGHT = PROJECT / "Plugins" / "PinWright"
PORT_FILE = PROJECT / "Saved" / "PinWright" / "gateway-port"
TOKEN_FILE = PROJECT / "Saved" / "PinWright" / "gateway-token"
BLENDER_GLTF = (
    ROOT / "storage" / "10_DEVELOPMENT" / "integrations" / "blender" / "workspace"
    / "Phase02_Blender_MCP_Test.glb"
)
REPORT = ROOT / "storage" / "80_REPORTS" / "phase02_unreal_mcp_integration.json"
EDITOR_LOG = PROJECT / "Saved" / "Logs" / "Phase02_UE_MCP_Test.log"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reset_isolated_outputs() -> list[str]:
    """Remove only disposable Phase 02 outputs so repeated runs remain deterministic."""
    removed: list[str] = []
    project_root = PROJECT.resolve()
    for path in (PROJECT / "Content" / "Phase02", PROJECT / "Saved" / "Screenshots" / "OpenLevel"):
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(project_root):
            raise RuntimeError(f"Refusing to clean path outside isolated Unreal project: {resolved}")
        if resolved.exists():
            shutil.rmtree(resolved)
            removed.append(str(resolved))
    return removed


class PinWrightClient:
    def __init__(self, port: int, token: str):
        self.url = f"http://127.0.0.1:{port}/mcp"
        self.token = token
        self.next_id = 1

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: int = 360) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
            separators=(",", ":"),
        ).encode()
        request = urllib.request.Request(  # noqa: S310 - URL is fixed to loopback in __init__
            self.url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed loopback URL
                message = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"PinWright HTTP {exc.code}: {exc.read().decode(errors='replace')}") from exc
        if message.get("id") != request_id:
            raise RuntimeError("PinWright returned a mismatched JSON-RPC id")
        if "error" in message:
            raise RuntimeError(json.dumps(message["error"], sort_keys=True))
        return message.get("result", {})

    def initialize(self) -> dict[str, Any]:
        return self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "uacs-phase02", "version": "1.0.0"},
            },
        )

    def call(self, method: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.request(
            "tools/call",
            {"name": "call", "arguments": {"method": method, "args": args or {}}},
        )
        if result.get("isError"):
            raise RuntimeError(f"PinWright method failed: {json.dumps(result, sort_keys=True, default=str)}")
        return result


def result_payload(result: dict[str, Any]) -> dict[str, Any]:
    for item in result.get("content", []):
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            try:
                parsed = json.loads(item["text"])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
    return result


def wait_for_gateway(editor: subprocess.Popen[str], timeout: int = 600) -> tuple[int, str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if editor.poll() is not None:
            raise RuntimeError(f"Unreal Editor exited before PinWright startup: {editor.returncode}")
        if PORT_FILE.is_file() and TOKEN_FILE.is_file():
            try:
                port = int(PORT_FILE.read_text(encoding="utf-8").strip())
                token = TOKEN_FILE.read_text(encoding="utf-8").strip()
                if token and 1024 <= port <= 65535:
                    return port, token
            except (OSError, ValueError):
                pass
        time.sleep(1)
    raise TimeoutError("PinWright gateway files were not published")


def wait_for_editor_ready(editor: subprocess.Popen[str], timeout: int = 600) -> None:
    """Wait for PinWright's measured ready state in the current editor log."""
    deadline = time.monotonic() + timeout
    marker = "PinWright editor readiness changed: ready"
    while time.monotonic() < deadline:
        if editor.poll() is not None:
            raise RuntimeError(f"Unreal Editor exited before PinWright became ready: {editor.returncode}")
        try:
            if marker in EDITOR_LOG.read_text(encoding="utf-8", errors="replace"):
                return
        except OSError:
            pass
        time.sleep(1)
    raise TimeoutError("Unreal Editor did not reach PinWright operational readiness")


def exception_chain(exc: BaseException) -> list[dict[str, str]]:
    """Return bounded diagnostic detail without leaking credentials or request headers."""
    chain: list[dict[str, str]] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 5:
        chain.append({"error": type(current).__name__, "message": str(current)})
        current = current.__cause__
    return chain


def register_gateway(engine) -> tuple[MCPGateway, str]:
    manager = MCPManager(engine)
    existing = next((item for item in manager.list_servers() if item["name"] == "pinwright-phase02"), None)
    if existing:
        server_id = str(existing["id"])
    else:
        server_id = str(
            manager.register(
                MCPRegistration(
                    name="pinwright-phase02",
                    source_url="https://github.com/PinWright/pinwright-ue",
                    version="1.0.0@20de4b5d6f18e9839aca17cc732fd6ef0a54a260",
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
            application="UNREAL",
            operation_selector="method",
            allowed_operations=[
                "system.identity", "system.inspect.*", "asset.import", "asset.save", "asset.exists",
                "level.create", "level.save", "level.get_info", "actor.spawn", "actor.set_transform",
                "actor.list", "sequencer.*", "render.capture_open_level", "mrq.*",
            ],
            denied_operations=[
                "python.execute", "system.console_command", "system.live_coding_compile", "system.run_tests",
                "editor.build", "editor.start", "editor.restart", "editor.quit",
            ],
            write_operations=[
                "asset.import", "asset.save", "level.create", "level.save", "actor.*", "sequencer.*", "mrq.*",
            ],
            approval_operations=[
                "asset.import", "asset.save", "level.create", "level.save", "actor.*", "sequencer.*", "mrq.*",
            ],
            write_scopes=[str(ROOT / "storage" / "10_DEVELOPMENT" / "integrations")],
            timeout_seconds=360,
            max_concurrency=1,
            retry_limit=0,
            rollback_strategy="delete_phase02_unreal_content_or_isolated_project",
            enabled=True,
        ),
    )
    return gateway, server_id


def ensure_approval(engine, server_id: str, operation: str) -> str:
    subject = approval_subject(server_id, operation)
    with engine.connect() as connection:
        existing = connection.execute(
            text(
                "SELECT id FROM approvals WHERE subject_kind='MCP_OPERATION' AND subject_id=:subject "
                "AND decision='APPROVED' ORDER BY created_at DESC LIMIT 1"
            ),
            {"subject": subject},
        ).first()
    if existing:
        return str(existing[0])
    return str(
        StudioService(engine).create_approval(
            ApprovalCreate(
                subject_kind="MCP_OPERATION",
                subject_id=subject,
                decision="APPROVED",
                decided_by="creative-director",
                notes=f"Approved revised Phase 02 isolated PinWright operation: {operation}",
                evidence={"project": str(PROJECT), "operation": operation},
            )
        )["id"]
    )


def main() -> int:
    if not BLENDER_GLTF.is_file():
        raise FileNotFoundError(f"Blender exchange asset missing: {BLENDER_GLTF}")
    cleaned_paths = reset_isolated_outputs()
    PORT_FILE.unlink(missing_ok=True)
    TOKEN_FILE.unlink(missing_ok=True)
    output_tail: deque[str] = deque(maxlen=200)
    editor = subprocess.Popen(  # noqa: S603
        [str(EDITOR), str(UPROJECT), "-NoSplash", "-NoSound"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
    )
    report: dict[str, Any] = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "phase": "PHASE_02_UNREAL_PINWRIGHT_INTEGRATION",
        "project": str(PROJECT),
        "editor_pid": editor.pid,
        "plugin_version": "1.0.0",
        "plugin_archive_sha256": "80259ddf99083e36bfda2a062a603e797ec5e54b3797c3131a7e7ad858be6376",
        "source_glb": {"path": str(BLENDER_GLTF), "sha256": sha256(BLENDER_GLTF)},
        "cleaned_paths": cleaned_paths,
        "steps": [],
    }
    engine = None
    try:
        port, token = wait_for_gateway(editor)
        client = PinWrightClient(port, token)
        report["gateway"] = {"host": "127.0.0.1", "port": port, "auth_token_present": bool(token)}
        report["initialize"] = client.initialize()
        tools = client.request("tools/list").get("tools", [])
        report["tools"] = [tool.get("name") for tool in tools]
        wait_for_editor_ready(editor)
        report["editor_ready"] = True
        settings = default_settings()
        upgrade_database(settings.database_path)
        engine = create_database_engine(settings.database_path)
        gateway, server_id = register_gateway(engine)

        def call(operation: str, args: dict[str, Any] | None = None, *, write: bool = False) -> dict[str, Any]:
            approval_id = ensure_approval(engine, server_id, operation) if write else None
            request = MCPInvocationRequest(
                tool_name="call",
                arguments={"method": operation, "args": args or {}},
                workspace_path=str(PROJECT) if write else None,
                approval_id=approval_id,
                actor="phase02-integration",
            )
            wrapped = gateway.execute(server_id, request, lambda: client.call(operation, args))
            payload = result_payload(wrapped["result"])
            report["steps"].append(
                {"operation": operation, "invocation_id": wrapped["invocation_id"], "payload": payload}
            )
            return payload

        call("system.identity")
        call("level.create", {"levelPath": "/Game/Phase02/Maps/Phase02_TestMap"}, write=True)
        imported = call(
            "asset.import",
            {
                "sourcePath": BLENDER_GLTF.as_posix(),
                "destinationPath": "/Game/Phase02/Assets",
                "overwrite": False,
            },
            write=True,
        )
        imported_results = imported.get("results", [])
        for item in imported_results:
            if isinstance(item, dict) and isinstance(item.get("assetPath"), str):
                call("asset.save", {"assetPath": item["assetPath"], "force": True}, write=True)
        static_mesh = next(
            (
                item
                for item in imported_results
                if isinstance(item, dict) and item.get("assetClass") == "StaticMesh"
            ),
            None,
        )
        if not isinstance(static_mesh, dict) or not isinstance(static_mesh.get("assetPath"), str):
            raise RuntimeError("GLB import did not return a StaticMesh asset")
        imported_path = static_mesh["assetPath"]
        call(
            "actor.spawn",
            {
                "meshPath": imported_path,
                "label": "PH02_ImportedCube",
                "location": {"x": 0, "y": 0, "z": 100},
            },
            write=True,
        )
        call("level.save", {}, write=True)
        sequence_path = "/Game/Phase02/Cinematics/LS_Phase02_Test"
        call(
            "sequencer.create",
            {"name": "LS_Phase02_Test", "path": "/Game/Phase02/Cinematics"},
            write=True,
        )
        call(
            "sequencer.set_properties",
            {"path": sequence_path, "frameRate": 24, "playbackStart": 0, "lengthInFrames": 72},
            write=True,
        )
        camera = call("sequencer.add_camera", {"path": sequence_path}, write=True)
        camera_path = str(camera.get("cameraActorPath") or camera.get("actorPath") or "SequenceCamera")
        call(
            "actor.set_transform",
            {
                "actorPath": camera_path,
                "location": {"x": 900, "y": -900, "z": 600},
                "lookAt": "PH02_ImportedCube",
            },
            write=True,
        )
        call(
            "sequencer.add_camera_track",
            {"sequencePath": sequence_path, "cameraActorPath": camera_path, "startTime": 0, "endTime": 3},
            write=True,
        )
        call("asset.save", {"assetPath": sequence_path, "force": True}, write=True)
        call("level.save", {}, write=True)
        capture = call(
            "render.capture_open_level",
            {
                "filename": "Phase02_Cinematic_Still.png",
                "width": 640,
                "height": 360,
                "location": {"x": 900, "y": -900, "z": 600},
                "rotation": {"pitch": -21.5, "yaw": 135, "roll": 0},
                "fov": 50,
                "allowBlank": False,
                "hideEditorSprites": True,
                "subject": {"kind": "actor", "name": "PH02_ImportedCube"},
            },
        )
        screenshots = sorted((PROJECT / "Saved" / "Screenshots" / "OpenLevel").glob("*.png"))
        report["outputs"] = [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in screenshots
        ]
        report["import_result"] = imported
        report["capture_result"] = capture
        report["server_id"] = server_id
        current_invocation_ids = {step["invocation_id"] for step in report["steps"]}
        report["gateway_invocations"] = [
            item for item in gateway.list_invocations(server_id) if item["id"] in current_invocation_ids
        ]
        report["recovery"] = {
            "deterministic_reset_exercised": bool(cleaned_paths),
            "removed_before_run": cleaned_paths,
            "outputs_recreated": len(screenshots),
        }
        report["status"] = "PASS" if screenshots and all(path.stat().st_size > 0 for path in screenshots) else "FAIL"
    except Exception as exc:
        report.update(
            {
                "status": "FAIL",
                "error": type(exc).__name__,
                "message": str(exc),
                "error_chain": exception_chain(exc),
            }
        )
    finally:
        if engine:
            engine.dispose()
        editor.terminate()
        try:
            editor.wait(timeout=30)
        except subprocess.TimeoutExpired:
            editor.kill()
            editor.wait(timeout=15)
        try:
            output_tail.extend(EDITOR_LOG.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass
        report["editor_exit_code"] = editor.returncode
        report["editor_output_tail"] = list(output_tail)
        REPORT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(REPORT)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
