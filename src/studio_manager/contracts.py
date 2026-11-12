from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
ShortText = Annotated[str, Field(min_length=1, max_length=160)]
Status = Literal["DRAFT", "ACTIVE", "ARCHIVED"]


class ProjectCreate(BaseModel):
    name: ShortText
    status: Status = "DRAFT"


class SeriesCreate(BaseModel):
    project_id: Identifier
    name: ShortText
    premise: Annotated[str | None, Field(max_length=2000)] = None
    status: Status = "DRAFT"


class EpisodeCreate(BaseModel):
    series_id: Identifier
    code: Identifier
    title: ShortText
    status: Status = "DRAFT"


class SceneCreate(BaseModel):
    episode_id: Identifier
    code: Identifier
    title: Annotated[str | None, Field(max_length=160)] = None
    status: Status = "DRAFT"


class ShotCreate(BaseModel):
    scene_id: Identifier
    code: Identifier
    frame_start: Annotated[int | None, Field(ge=0)] = None
    frame_end: Annotated[int | None, Field(ge=0)] = None
    fps: Annotated[float | None, Field(gt=0, le=240)] = None
    status: Status = "DRAFT"

    @model_validator(mode="after")
    def frame_range_is_ordered(self) -> ShotCreate:
        if self.frame_start is not None and self.frame_end is not None and self.frame_end < self.frame_start:
            raise ValueError("frame_end must be greater than or equal to frame_start")
        return self


class CharacterCreate(BaseModel):
    project_id: Identifier
    code: Identifier
    name: ShortText
    bible_status: Status = "DRAFT"


class AssetCreate(BaseModel):
    project_id: Identifier
    code: Identifier
    name: ShortText
    asset_type: Literal["CHARACTER", "ENVIRONMENT", "PROP", "MATERIAL", "RIG", "ANIMATION", "AUDIO", "OTHER"]
    lifecycle_state: Literal["DRAFT", "VALIDATING", "PENDING_APPROVAL", "APPROVED", "PUBLISHED", "RETIRED"] = "DRAFT"
    protected: bool = False


class AssetVersionCreate(BaseModel):
    workspace_path: str
    status: Literal["DRAFT"] = "DRAFT"
    sha256: Annotated[str | None, Field(pattern=r"^[a-f0-9]{64}$")] = None


class AssetVersionTransition(BaseModel):
    target_status: Literal["VALIDATING", "PENDING_APPROVAL"]


class JobCreate(BaseModel):
    project_id: Identifier
    job_type: Identifier
    workspace_path: str
    requested_by: ShortText
    target_application: Literal["BLENDER", "UNREAL", "NONE"] = "NONE"


class JobTransition(BaseModel):
    target_status: Literal[
        "QUEUED", "RUNNING", "VALIDATING", "PENDING_APPROVAL", "APPROVED", "PUBLISHED",
        "FAILED", "BLOCKED", "CANCELLED", "ROLLED_BACK",
    ]
    actor: ShortText
    payload: dict[str, object] = Field(default_factory=dict)
    approval_id: Identifier | None = None


class ApprovalCreate(BaseModel):
    subject_kind: Literal["JOB", "ASSET_VERSION", "CHARACTER_VERSION", "MCP_OPERATION"]
    subject_id: Identifier
    decision: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    decided_by: ShortText
    notes: Annotated[str | None, Field(max_length=4000)] = None
    evidence: dict[str, object] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: ShortText | None = None
    status: Status | None = None


class AssetUpdate(BaseModel):
    name: ShortText | None = None
    lifecycle_state: (
        Literal["DRAFT", "VALIDATING", "PENDING_APPROVAL", "APPROVED", "PUBLISHED", "RETIRED"] | None
    ) = None
    protected: bool | None = None


class CharacterUpdate(BaseModel):
    name: ShortText | None = None
    bible_status: Status | None = None


class CharacterVariantCreate(BaseModel):
    code: Identifier
    name: ShortText
    description: Annotated[str | None, Field(max_length=2000)] = None
    config: dict[str, object] = Field(default_factory=dict)
    status: Status = "DRAFT"


class CharacterVariantUpdate(BaseModel):
    name: ShortText | None = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    config: dict[str, object] | None = None
    status: Status | None = None


class ImportRequest(BaseModel):
    source_kind: Literal["PHASE02_SKILLS", "PHASE02_REPORT"]
    source_path: str
    dry_run: bool = True
