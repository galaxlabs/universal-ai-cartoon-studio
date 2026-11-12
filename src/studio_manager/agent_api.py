"""Authenticated inert registry endpoints. Metadata registration is not execution."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from studio_manager.agent_contracts import AgentCreate, AgentVersionCreate, SkillCreate, SkillVersionCreate
from studio_manager.agent_registry import MAX_REGISTRY_OFFSET, AgentRegistry
from studio_manager.auth import require_api_token


class RegistryRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def without_private_input_echo(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                # Never echo instructions/config or non-finite floats in errors.
                errors = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": errors})

        return without_private_input_echo


router = APIRouter(
    prefix="/api/v1", tags=["Agent & Skill Registry"],
    dependencies=[Depends(require_api_token)], route_class=RegistryRoute,
)
Principal = Annotated[str, Depends(require_api_token)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=MAX_REGISTRY_OFFSET)]


def registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


Registry = Annotated[AgentRegistry, Depends(registry)]


@router.get("/agents")
def list_agents(service: Registry, limit: Limit = 50, offset: Offset = 0):
    return service.list_agents(limit, offset)


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def create_agent(payload: AgentCreate, service: Registry, actor: Principal):
    return service.create_agent(**payload.model_dump(), actor=actor)


@router.get("/agents/{agent_id}/versions")
def list_agent_versions(agent_id: str, service: Registry, limit: Limit = 50, offset: Offset = 0):
    return service.list_versions("agent", agent_id, limit, offset)


@router.post("/agents/{agent_id}/versions", status_code=status.HTTP_201_CREATED)
def create_agent_version(agent_id: str, payload: AgentVersionCreate, service: Registry, actor: Principal):
    return service.create_agent_version(agent_id, **payload.model_dump(), actor=actor)


@router.get("/skills")
def list_skills(service: Registry, limit: Limit = 50, offset: Offset = 0):
    return service.list_skills(limit, offset)


@router.get("/skills/legacy")
def list_legacy_skills(service: Registry, limit: Limit = 50, offset: Offset = 0):
    return service.list_legacy_skills(limit, offset)


@router.post("/skills", status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillCreate, service: Registry, actor: Principal):
    return service.create_skill(**payload.model_dump(), actor=actor)


@router.get("/skills/{skill_id}/versions")
def list_skill_versions(skill_id: str, service: Registry, limit: Limit = 50, offset: Offset = 0):
    return service.list_versions("skill", skill_id, limit, offset)


@router.post("/skills/{skill_id}/versions", status_code=status.HTTP_201_CREATED)
def create_skill_version(skill_id: str, payload: SkillVersionCreate, service: Registry, actor: Principal):
    return service.create_skill_version(skill_id, **payload.model_dump(), actor=actor)
