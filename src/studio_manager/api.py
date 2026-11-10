from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from studio_manager.contracts import (
    ApprovalCreate,
    AssetCreate,
    AssetVersionCreate,
    CharacterCreate,
    EpisodeCreate,
    JobCreate,
    JobTransition,
    ProjectCreate,
    SceneCreate,
    SeriesCreate,
    ShotCreate,
)
from studio_manager.mcp_gateway import (
    MCPGateway,
    MCPGatewayPolicy,
    MCPInvocationCompletion,
    MCPInvocationRequest,
)
from studio_manager.mcp_manager import MCPManager, MCPRegistration
from studio_manager.service import StudioService

router = APIRouter(prefix="/api")


def service(request: Request) -> StudioService:
    return request.app.state.service


def mcp(request: Request) -> MCPManager:
    return request.app.state.mcp


def gateway(request: Request) -> MCPGateway:
    return request.app.state.mcp_gateway


StudioDep = Annotated[StudioService, Depends(service)]
MCPDep = Annotated[MCPManager, Depends(mcp)]
GatewayDep = Annotated[MCPGateway, Depends(gateway)]


@router.get("/studio")
def studio_snapshot(studio: StudioDep) -> dict[str, object]:
    return studio.snapshot()


@router.post("/catalog/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_project(payload)


@router.post("/catalog/series", status_code=status.HTTP_201_CREATED)
def create_series(payload: SeriesCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_series(payload)


@router.post("/catalog/episodes", status_code=status.HTTP_201_CREATED)
def create_episode(payload: EpisodeCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_episode(payload)


@router.post("/catalog/scenes", status_code=status.HTTP_201_CREATED)
def create_scene(payload: SceneCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_scene(payload)


@router.post("/catalog/shots", status_code=status.HTTP_201_CREATED)
def create_shot(payload: ShotCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_shot(payload)


@router.post("/characters", status_code=status.HTTP_201_CREATED)
def create_character(payload: CharacterCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_character(payload)


@router.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_asset(payload)


@router.post("/assets/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
def create_asset_version(
    asset_id: str,
    payload: AssetVersionCreate,
    studio: StudioDep,
) -> dict[str, object]:
    return studio.create_asset_version(asset_id, payload)


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_job(payload)


@router.post("/jobs/{job_id}/transitions")
def transition_job(
    job_id: str,
    payload: JobTransition,
    studio: StudioDep,
) -> dict[str, object]:
    return studio.transition_job(job_id, payload)


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
def create_approval(payload: ApprovalCreate, studio: StudioDep) -> dict[str, object]:
    return studio.create_approval(payload)


@router.get("/mcp/servers")
def list_mcp_servers(manager: MCPDep) -> dict[str, object]:
    servers = manager.list_servers()
    return {"servers": servers, "count": len(servers), "activation_exposed": False}


@router.post("/mcp/servers", status_code=status.HTTP_201_CREATED)
def register_mcp_server(payload: MCPRegistration, manager: MCPDep) -> dict[str, object]:
    return manager.register(payload)


@router.get("/mcp/servers/{server_id}/activation-check")
def mcp_activation_check(server_id: str, manager: MCPDep) -> dict[str, object]:
    return manager.activation_check(server_id)


@router.put("/mcp/servers/{server_id}/gateway-policy")
def set_mcp_gateway_policy(
    server_id: str,
    payload: MCPGatewayPolicy,
    policy_gateway: GatewayDep,
) -> dict[str, object]:
    return policy_gateway.set_policy(server_id, payload)


@router.post("/mcp/servers/{server_id}/invocations", status_code=status.HTTP_201_CREATED)
def authorize_mcp_invocation(
    server_id: str,
    payload: MCPInvocationRequest,
    policy_gateway: GatewayDep,
) -> dict[str, object]:
    return policy_gateway.begin(server_id, payload)


@router.post("/mcp/invocations/{invocation_id}/complete")
def complete_mcp_invocation(
    invocation_id: str,
    payload: MCPInvocationCompletion,
    policy_gateway: GatewayDep,
) -> dict[str, object]:
    return policy_gateway.complete(invocation_id, payload)


@router.get("/mcp/invocations")
def list_mcp_invocations(policy_gateway: GatewayDep, server_id: str | None = None) -> dict[str, object]:
    invocations = policy_gateway.list_invocations(server_id)
    return {"invocations": invocations, "count": len(invocations)}
