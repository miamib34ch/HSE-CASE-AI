from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str = ""


class ProjectRead(ORMModel):
    id: str
    name: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class RequirementUploadRequest(BaseModel):
    content: str = Field(min_length=10)
    source_type: str = "text"
    filename: str = "requirements.md"


class RequirementDraftRequest(BaseModel):
    description: str = Field(min_length=10)
    auto_structure: bool = True
    model: str | None = None
    provider: str | None = None
    generation_mode: str = "auto"


class RequirementStructureRead(ORMModel):
    id: str
    project_id: str
    version: int
    structured_json: dict[str, Any]
    markdown_content: str
    is_confirmed: bool
    created_at: datetime


class StructureConfirmRequest(BaseModel):
    approved: bool = False
    markdown_content: str | None = None
    structured_json: dict[str, Any] | None = None


class RequirementDraftResponse(BaseModel):
    document_id: str
    content: str
    structure: RequirementStructureRead | None = None


class GenerationRequest(BaseModel):
    approved: bool = False
    provider: str | None = None
    model: str | None = None
    generation_mode: str = "auto"


class DeployRequest(BaseModel):
    approved: bool = False
    dry_run: bool | None = None


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=3)
    provider: str | None = None
    model: str | None = None
    apply_changes: bool = False
    approved: bool = False


class AssistantFileChange(BaseModel):
    path: str
    reason: str
    content: str


class AssistantContextItem(BaseModel):
    name: str
    source_type: str
    included: bool
    note: str | None = None


class AssistantChatResponse(BaseModel):
    reply: str
    used_provider: str
    used_model: str
    applied_paths: list[str] = Field(default_factory=list)
    suggested_paths: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
    changes: list[AssistantFileChange] = Field(default_factory=list)
    context_items: list[AssistantContextItem] = Field(default_factory=list)


class RunRead(ORMModel):
    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None


class ArtifactRead(BaseModel):
    id: str
    name: str
    artifact_type: str
    path: str
    version: int
    size_bytes: int
    is_text: bool
    is_image: bool
    download_url: str


class ArtifactDetail(ArtifactRead):
    content: str | None = None
    encoding: str | None = None


class ArtifactTextUpdate(BaseModel):
    content: str
