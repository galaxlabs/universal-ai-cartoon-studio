from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from studio_manager.config import PROJECT_ROOT
from studio_manager.contracts import ApprovalCreate, AssetCreate, JobCreate, JobTransition, ProjectCreate
from studio_manager.service import StudioService

router = APIRouter()
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "src" / "studio_manager" / "templates"))


def service(request: Request) -> StudioService:
    return request.app.state.service


StudioDep = Annotated[StudioService, Depends(service)]


def context(request: Request, studio: StudioService) -> dict[str, object]:
    return {
        "request": request,
        "snapshot": studio.snapshot(),
        "default_workspace": str(PROJECT_ROOT / "storage" / "10_DEVELOPMENT" / "jobs"),
    }


def workspace_partial(request: Request, studio: StudioService) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="partials/workspace_content.html",
        context=context(request, studio),
    )


@router.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request, studio: StudioDep) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="workspace.html",
        context=context(request, studio),
    )


@router.post("/ui/projects", response_class=HTMLResponse)
def create_project(
    request: Request,
    name: Annotated[str, Form(min_length=1, max_length=160)],
    studio: StudioDep,
) -> HTMLResponse:
    studio.create_project(ProjectCreate(name=name))
    return workspace_partial(request, studio)


@router.post("/ui/assets", response_class=HTMLResponse)
def create_asset(
    request: Request,
    project_id: Annotated[str, Form()],
    code: Annotated[str, Form()],
    name: Annotated[str, Form()],
    asset_type: Annotated[str, Form()],
    studio: StudioDep,
) -> HTMLResponse:
    studio.create_asset(
        AssetCreate(project_id=project_id, code=code, name=name, asset_type=asset_type)  # type: ignore[arg-type]
    )
    return workspace_partial(request, studio)


@router.post("/ui/jobs", response_class=HTMLResponse)
def create_job(
    request: Request,
    project_id: Annotated[str, Form()],
    job_type: Annotated[str, Form()],
    workspace_path: Annotated[str, Form()],
    studio: StudioDep,
) -> HTMLResponse:
    studio.create_job(
        JobCreate(
            project_id=project_id,
            job_type=job_type,
            workspace_path=workspace_path,
            requested_by="creative-director",
        )
    )
    return workspace_partial(request, studio)


@router.post("/ui/jobs/{job_id}/transitions", response_class=HTMLResponse)
def transition_job(
    request: Request,
    job_id: str,
    target_status: Annotated[str, Form()],
    studio: StudioDep,
) -> HTMLResponse:
    studio.transition_job(
        job_id,
        JobTransition(target_status=target_status, actor="creative-director"),  # type: ignore[arg-type]
    )
    return workspace_partial(request, studio)


@router.post("/ui/approvals", response_class=HTMLResponse)
def create_approval(
    request: Request,
    subject_id: Annotated[str, Form()],
    decision: Annotated[str, Form()],
    studio: StudioDep,
    notes: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    studio.create_approval(
        ApprovalCreate(
            subject_kind="JOB",
            subject_id=subject_id,
            decision=decision,  # type: ignore[arg-type]
            decided_by="creative-director",
            notes=notes,
        )
    )
    return workspace_partial(request, studio)
