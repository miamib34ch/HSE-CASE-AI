from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_artifact_service,
    get_audit_service,
    get_correlation_id,
    get_db,
    get_deployment_service,
    get_generation_service,
    get_project_assistant_service,
    get_project_service,
    get_provider_registry_with_db,
    get_requirement_service,
    get_test_service,
)
from app.db.models import DeploymentRun, GenerationRun, TestRun
from app.domain.enums.common import ArtifactType, TaskType
from app.providers.registry import ProviderRegistry
from app.schemas.projects import (
    ArtifactDetail,
    ArtifactRead,
    ArtifactTextUpdate,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantContextItem,
    AssistantFileChange,
    DeployRequest,
    GenerationRequest,
    ProjectCreate,
    ProjectRead,
    RequirementDraftRequest,
    RequirementDraftResponse,
    RequirementStructureRead,
    RequirementUploadRequest,
    RunRead,
    StructureConfirmRequest,
)
from app.services.artifacts import ArtifactService
from app.services.audit import AuditService
from app.services.deployment import DeploymentService
from app.services.generation import GenerationService
from app.services.project_assistant import ProjectAssistantService
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.services.testing import TestService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service),
    audit_service: AuditService = Depends(get_audit_service),
    correlation_id: str = Depends(get_correlation_id),
) -> ProjectRead:
    project = project_service.create_project(name=payload.name, description=payload.description)
    audit_service.log(
        event_type="project.created",
        correlation_id=correlation_id,
        project_id=project.id,
        details={"name": project.name},
    )
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
def list_projects(project_service: ProjectService = Depends(get_project_service)) -> list[ProjectRead]:
    return [ProjectRead.model_validate(project) for project in project_service.list_projects()]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str, project_service: ProjectService = Depends(get_project_service)
) -> ProjectRead:
    try:
        project = project_service.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProjectRead.model_validate(project)


@router.post("/{project_id}/requirements/raw")
def upload_requirements(
    project_id: str,
    payload: RequirementUploadRequest,
    requirement_service: RequirementService = Depends(get_requirement_service),
    audit_service: AuditService = Depends(get_audit_service),
    correlation_id: str = Depends(get_correlation_id),
) -> dict[str, str]:
    try:
        document = requirement_service.upload(
            project_id=project_id,
            content=payload.content,
            source_type=payload.source_type,
            filename=payload.filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_service.log(
        event_type="requirements.uploaded",
        correlation_id=correlation_id,
        project_id=project_id,
        details={"document_id": document.id},
    )
    return {"document_id": document.id, "status": "uploaded"}


@router.post("/{project_id}/requirements/draft", response_model=RequirementDraftResponse)
def draft_requirements(
    project_id: str,
    payload: RequirementDraftRequest,
    requirement_service: RequirementService = Depends(get_requirement_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
    audit_service: AuditService = Depends(get_audit_service),
    correlation_id: str = Depends(get_correlation_id),
) -> RequirementDraftResponse:
    adapter = registry.get(payload.provider)
    try:
        document, structure = requirement_service.draft_from_description(
            project_id=project_id,
            description=payload.description,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.REQUIREMENTS_ANALYSIS.value),
            correlation_id=correlation_id,
            auto_structure=payload.auto_structure,
            generation_mode=payload.generation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_service.log(
        event_type="requirements.drafted",
        correlation_id=correlation_id,
        project_id=project_id,
        details={"document_id": document.id, "auto_structure": payload.auto_structure},
    )
    return RequirementDraftResponse(
        document_id=document.id,
        content=document.content,
        structure=RequirementStructureRead.model_validate(structure) if structure is not None else None,
    )


@router.post("/{project_id}/requirements/structure", response_model=RequirementStructureRead)
def structure_requirements(
    project_id: str,
    payload: GenerationRequest,
    requirement_service: RequirementService = Depends(get_requirement_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
    correlation_id: str = Depends(get_correlation_id),
) -> RequirementStructureRead:
    adapter = registry.get(payload.provider)
    try:
        structure = requirement_service.structure(
            project_id=project_id,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.REQUIREMENTS_ANALYSIS.value),
            correlation_id=correlation_id,
            generation_mode=payload.generation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RequirementStructureRead.model_validate(structure)


@router.post("/{project_id}/requirements/confirm", response_model=RequirementStructureRead)
def confirm_structure(
    project_id: str,
    payload: StructureConfirmRequest,
    requirement_service: RequirementService = Depends(get_requirement_service),
) -> RequirementStructureRead:
    try:
        structure = requirement_service.confirm(
            project_id=project_id,
            approved=payload.approved,
            markdown_content=payload.markdown_content,
            structured_json=payload.structured_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RequirementStructureRead.model_validate(structure)


@router.get("/{project_id}/requirements/structure/latest", response_model=RequirementStructureRead | None)
def latest_structure(
    project_id: str,
    requirement_service: RequirementService = Depends(get_requirement_service),
) -> RequirementStructureRead | None:
    structure = requirement_service.latest_structure(project_id)
    return RequirementStructureRead.model_validate(structure) if structure is not None else None


@router.post("/{project_id}/generate/code", response_model=RunRead)
def generate_code(
    project_id: str,
    payload: GenerationRequest,
    generation_service: GenerationService = Depends(get_generation_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
    correlation_id: str = Depends(get_correlation_id),
) -> RunRead:
    adapter = registry.get(payload.provider)
    try:
        run = generation_service.generate_code(
            project_id=project_id,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.CODE_GENERATION.value),
            correlation_id=correlation_id,
            approved=payload.approved,
            generation_mode=payload.generation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunRead.model_validate(run)


@router.post("/{project_id}/generate/tests")
def generate_tests(
    project_id: str,
    payload: GenerationRequest,
    test_service: TestService = Depends(get_test_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
) -> dict[str, str]:
    adapter = registry.get(payload.provider)
    try:
        test_run = test_service.generate_tests(
            project_id=project_id,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.TEST_GENERATION.value),
            approved=payload.approved,
            generation_mode=payload.generation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"test_run_id": test_run.id, "status": test_run.status}


@router.post("/{project_id}/generate/schemas", response_model=RunRead)
def generate_schemas(
    project_id: str,
    payload: GenerationRequest,
    generation_service: GenerationService = Depends(get_generation_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
    correlation_id: str = Depends(get_correlation_id),
) -> RunRead:
    adapter = registry.get(payload.provider)
    try:
        run = generation_service.generate_schemas(
            project_id=project_id,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.SCHEMA_GENERATION.value),
            correlation_id=correlation_id,
            approved=payload.approved,
            generation_mode=payload.generation_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunRead.model_validate(run)


@router.post("/{project_id}/deploy")
def run_deploy(
    project_id: str,
    payload: DeployRequest,
    deployment_service: DeploymentService = Depends(get_deployment_service),
) -> dict[str, object]:
    try:
        deployment = deployment_service.deploy(
            project_id=project_id,
            approved=payload.approved,
            dry_run=payload.dry_run if payload.dry_run is not None else True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "deployment_run_id": deployment.id,
        "status": deployment.status,
        "dry_run": deployment.dry_run,
        "logs": deployment.logs,
        "target_path": deployment.target_path,
    }


@router.post("/{project_id}/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    project_id: str,
    payload: AssistantChatRequest,
    assistant_service: ProjectAssistantService = Depends(get_project_assistant_service),
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
) -> AssistantChatResponse:
    adapter = registry.get(payload.provider)
    try:
        result = assistant_service.chat(
            project_id=project_id,
            message=payload.message,
            adapter=adapter,
            model=payload.model or registry.default_model_for(adapter.provider_name, TaskType.CODE_GENERATION.value),
            apply_changes=payload.apply_changes,
            approved=payload.approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssistantChatResponse(
        reply=result.reply,
        used_provider=result.used_provider,
        used_model=result.used_model,
        applied_paths=result.applied_paths,
        suggested_paths=result.suggested_paths,
        fallback_reason=result.fallback_reason,
        changes=[
            AssistantFileChange(path=change.path, reason=change.reason, content=change.content)
            for change in result.changes
        ],
        context_items=[
            AssistantContextItem(
                name=item.name,
                source_type=item.source_type,
                included=item.included,
                note=item.note,
            )
            for item in result.context_items
        ],
    )


@router.get("/{project_id}/artifacts", response_model=list[ArtifactRead])
def list_artifacts(
    project_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> list[ArtifactRead]:
    return [
        ArtifactRead(
            id=artifact.id,
            name=artifact.name,
            artifact_type=artifact.artifact_type,
            path=artifact.path,
            version=artifact.version,
            size_bytes=artifact.size_bytes,
            is_text=artifact_service.is_text_artifact(artifact),
            is_image=artifact_service.is_image_artifact(artifact),
            download_url=f"/api/projects/{project_id}/artifacts/{artifact.id}/download",
        )
        for artifact in artifact_service.list_artifacts(project_id)
    ]


@router.post("/{project_id}/artifacts/upload", response_model=ArtifactRead)
async def upload_artifact(
    project_id: str,
    file: UploadFile = File(...),
    artifact_type: str = Form(default=ArtifactType.MANUAL_UPLOAD.value),
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRead:
    content = await file.read()
    try:
        artifact = artifact_service.upload_bytes(
            project_id=project_id,
            filename=file.filename or "artifact.bin",
            content=content,
            artifact_type=ArtifactType(artifact_type),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ArtifactRead(
        id=artifact.id,
        name=artifact.name,
        artifact_type=artifact.artifact_type,
        path=artifact.path,
        version=artifact.version,
        size_bytes=artifact.size_bytes,
        is_text=artifact_service.is_text_artifact(artifact),
        is_image=artifact_service.is_image_artifact(artifact),
        download_url=f"/api/projects/{project_id}/artifacts/{artifact.id}/download",
    )


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=ArtifactDetail)
def get_artifact(
    project_id: str,
    artifact_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactDetail:
    try:
        artifact = artifact_service.get_artifact(project_id, artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ArtifactDetail(
        id=artifact.id,
        name=artifact.name,
        artifact_type=artifact.artifact_type,
        path=artifact.path,
        version=artifact.version,
        size_bytes=artifact.size_bytes,
        is_text=artifact_service.is_text_artifact(artifact),
        is_image=artifact_service.is_image_artifact(artifact),
        download_url=f"/api/projects/{project_id}/artifacts/{artifact.id}/download",
        content=artifact_service.read_text_content(artifact),
        encoding="utf-8" if artifact_service.is_text_artifact(artifact) else None,
    )


@router.put("/{project_id}/artifacts/{artifact_id}/text", response_model=ArtifactRead)
def update_text_artifact(
    project_id: str,
    artifact_id: str,
    payload: ArtifactTextUpdate,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> ArtifactRead:
    try:
        artifact = artifact_service.update_text_artifact(
            project_id=project_id,
            artifact_id=artifact_id,
            content=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ArtifactRead(
        id=artifact.id,
        name=artifact.name,
        artifact_type=artifact.artifact_type,
        path=artifact.path,
        version=artifact.version,
        size_bytes=artifact.size_bytes,
        is_text=artifact_service.is_text_artifact(artifact),
        is_image=artifact_service.is_image_artifact(artifact),
        download_url=f"/api/projects/{project_id}/artifacts/{artifact.id}/download",
    )


@router.delete("/{project_id}/artifacts/{artifact_id}")
def delete_artifact(
    project_id: str,
    artifact_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> dict[str, str]:
    try:
        deleted = artifact_service.delete_artifact(project_id, artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "deleted" if deleted else "already_deleted"}


@router.get("/{project_id}/artifacts/{artifact_id}/download")
def download_artifact(
    project_id: str,
    artifact_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
) -> FileResponse:
    try:
        artifact = artifact_service.get_artifact(project_id, artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    path = Path(artifact.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл артефакта не найден")
    return FileResponse(path=path, filename=artifact.name)


@router.get("/{project_id}/runs")
def list_runs(project_id: str, db: Session = Depends(get_db)) -> dict[str, list[dict[str, object]]]:
    generation_runs = list(
        db.scalars(select(GenerationRun).where(GenerationRun.project_id == project_id))
    )
    test_runs = list(db.scalars(select(TestRun).where(TestRun.project_id == project_id)))
    deploy_runs = list(db.scalars(select(DeploymentRun).where(DeploymentRun.project_id == project_id)))
    return {
        "generation_runs": [
            {"id": run.id, "task_type": run.task_type, "status": run.status, "provider": run.provider}
            for run in generation_runs
        ],
        "test_runs": [
            {"id": run.id, "status": run.status, "passed": run.passed, "failed": run.failed}
            for run in test_runs
        ],
        "deployment_runs": [
            {"id": run.id, "status": run.status, "dry_run": run.dry_run} for run in deploy_runs
        ],
    }


@router.get("/{project_id}/summary")
def project_summary(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
) -> dict[str, object]:
    try:
        return project_service.summary(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/generation/logs")
def generation_logs(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    runs = list(
        db.scalars(
            select(GenerationRun)
            .where(GenerationRun.project_id == project_id)
            .order_by(GenerationRun.started_at.desc())
        )
    )
    return [
        {
            "id": run.id,
            "task_type": run.task_type,
            "status": run.status,
            "provider": run.provider,
            "model": run.model,
            "error_message": run.error_message,
            "output_payload": run.output_payload,
        }
        for run in runs
    ]


@router.get("/{project_id}/test-results")
def test_results(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    runs = list(db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.started_at.desc())))
    return [
        {
            "id": run.id,
            "status": run.status,
            "passed": run.passed,
            "failed": run.failed,
            "skipped": run.skipped,
            "logs": run.logs,
            "junit_path": run.junit_path,
            "coverage_summary": run.coverage_summary,
        }
        for run in runs
    ]


@router.get("/{project_id}/deploy-status")
def deploy_status(project_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    latest_generation = db.scalar(
        select(GenerationRun)
        .where(
            GenerationRun.project_id == project_id,
            GenerationRun.task_type == TaskType.CODE_GENERATION.value,
        )
        .order_by(GenerationRun.started_at.desc())
        .limit(1)
    )
    preview_url = None
    if latest_generation is not None:
        preview_url = dict(latest_generation.output_payload).get("preview_url")
    runs = list(
        db.scalars(
            select(DeploymentRun).where(DeploymentRun.project_id == project_id).order_by(DeploymentRun.started_at.desc())
        )
    )
    return [
        {
            "id": run.id,
            "status": run.status,
            "logs": run.logs,
            "dry_run": run.dry_run,
            "target_path": run.target_path,
            "preview_url": preview_url,
        }
        for run in runs
    ]
