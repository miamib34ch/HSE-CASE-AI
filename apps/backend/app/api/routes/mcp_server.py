from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_correlation_id,
    get_db,
    get_deployment_service,
    get_project_service,
    get_provider_registry,
    get_requirement_service,
    get_test_service,
)
from app.db.models import (
    DeploymentRun,
    GeneratedArtifact,
    GenerationRun,
    RequirementDocument,
    RequirementStructure,
    TestRun,
)
from app.providers.registry import ProviderRegistry
from app.schemas.projects import ProjectCreate
from app.services.deployment import DeploymentService
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.services.testing import TestService

router = APIRouter(prefix="/mcp/server", tags=["mcp-server"])


@router.get("/tools")
def mcp_tools() -> dict[str, object]:
    return {
        "tools": [
            {"name": "create_project", "description": "Создать проект", "side_effect": True},
            {"name": "list_projects", "description": "Список проектов", "side_effect": False},
            {"name": "upload_requirements", "description": "Загрузить требования", "side_effect": True},
            {"name": "structure_requirements", "description": "Структурировать требования", "side_effect": True},
            {"name": "confirm_requirement_structure", "description": "Подтвердить структуру", "side_effect": True},
            {"name": "generate_code", "description": "Сгенерировать код", "side_effect": True},
            {"name": "generate_tests", "description": "Сгенерировать тесты", "side_effect": True},
            {"name": "run_deploy", "description": "Запустить deploy", "side_effect": True},
            {"name": "get_project_status", "description": "Статус проекта", "side_effect": False},
            {"name": "list_artifacts", "description": "Артефакты проекта", "side_effect": False},
            {"name": "get_generation_logs", "description": "Логи генерации", "side_effect": False},
            {"name": "get_test_results", "description": "Результаты тестов", "side_effect": False},
            {"name": "get_deploy_status", "description": "Статус деплоя", "side_effect": False},
        ]
    }


@router.get("/resources")
def mcp_resources() -> dict[str, object]:
    return {
        "resources": [
            {"uri": "project://{project_id}/requirements/raw", "description": "Сырые требования"},
            {"uri": "project://{project_id}/requirements/structured", "description": "Структурированные требования"},
            {"uri": "project://{project_id}/artifacts", "description": "Артефакты проекта"},
            {"uri": "project://{project_id}/runs", "description": "Запуски pipeline"},
            {"uri": "project://{project_id}/summary", "description": "Краткая сводка"},
        ]
    }


@router.get("/prompts")
def mcp_prompts() -> dict[str, object]:
    return {
        "prompts": [
            {"name": "analyze_requirements", "description": "Промпт анализа требований"},
            {"name": "generate_backend_code", "description": "Промпт генерации backend"},
            {"name": "generate_frontend_code", "description": "Промпт генерации frontend"},
            {"name": "generate_tests", "description": "Промпт генерации тестов"},
            {"name": "review_architecture", "description": "Промпт архитектурного review"},
        ]
    }


@router.post("/tools/create_project")
def mcp_create_project(
    payload: ProjectCreate, project_service: ProjectService = Depends(get_project_service)
) -> dict[str, object]:
    project = project_service.create_project(name=payload.name, description=payload.description)
    return {"project_id": project.id, "status": project.status}


@router.post("/tools/upload_requirements")
def mcp_upload_requirements(
    payload: dict[str, str],
    requirement_service: RequirementService = Depends(get_requirement_service),
) -> dict[str, object]:
    document = requirement_service.upload(
        project_id=payload["project_id"],
        content=payload["content"],
        source_type=payload.get("source_type", "text"),
        filename=payload.get("filename", "requirements.md"),
    )
    return {"document_id": document.id}


@router.post("/tools/structure_requirements")
def mcp_structure_requirements(
    payload: dict[str, str],
    requirement_service: RequirementService = Depends(get_requirement_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
    correlation_id: str = Depends(get_correlation_id),
) -> dict[str, object]:
    structure = requirement_service.structure(
        project_id=payload["project_id"],
        adapter=registry.get(),
        model="demo-analysis-v1",
        correlation_id=correlation_id,
    )
    return {"structure_id": structure.id, "markdown_content": structure.markdown_content}


@router.post("/tools/confirm_requirement_structure")
def mcp_confirm_requirement_structure(
    payload: dict[str, object],
    requirement_service: RequirementService = Depends(get_requirement_service),
) -> dict[str, object]:
    markdown_content = payload.get("markdown_content")
    structured_json = payload.get("structured_json")
    structure = requirement_service.confirm(
        project_id=str(payload["project_id"]),
        approved=bool(payload.get("approved", False)),
        markdown_content=markdown_content if isinstance(markdown_content, str) else None,
        structured_json=structured_json if isinstance(structured_json, dict) else None,
    )
    return {"structure_id": structure.id, "is_confirmed": structure.is_confirmed}


@router.get("/tools/list_projects")
def mcp_list_projects(project_service: ProjectService = Depends(get_project_service)) -> dict[str, object]:
    return {
        "projects": [
            {"id": project.id, "name": project.name, "status": project.status}
            for project in project_service.list_projects()
        ]
    }


@router.get("/tools/get_project_status/{project_id}")
def mcp_get_project_status(
    project_id: str, project_service: ProjectService = Depends(get_project_service)
) -> dict[str, object]:
    try:
        project = project_service.get_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"project_id": project.id, "status": project.status}


@router.post("/tools/generate_code")
def mcp_generate_code(
    payload: dict[str, object],
    project_service: ProjectService = Depends(get_project_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
    correlation_id: str = Depends(get_correlation_id),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from app.config.settings import get_settings
    from app.infrastructure.storage.artifact_storage import ArtifactStorage
    from app.services.generation import GenerationService

    generation_service = GenerationService(db, ArtifactStorage(get_settings()), project_service)
    run = generation_service.generate_code(
        project_id=str(payload["project_id"]),
        adapter=registry.get(),
        model=str(payload.get("model", "demo-code-v1")),
        correlation_id=correlation_id,
        approved=bool(payload.get("approved", False)),
    )
    return {"run_id": run.id, "status": run.status}


@router.post("/tools/generate_tests")
def mcp_generate_tests(
    payload: dict[str, object],
    test_service: TestService = Depends(get_test_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> dict[str, object]:
    run = test_service.generate_tests(
        project_id=str(payload["project_id"]),
        adapter=registry.get(),
        model=str(payload.get("model", "demo-test-v1")),
        approved=bool(payload.get("approved", False)),
    )
    return {"test_run_id": run.id, "status": run.status}


@router.post("/tools/run_deploy")
def mcp_run_deploy(
    payload: dict[str, object],
    deployment_service: DeploymentService = Depends(get_deployment_service),
) -> dict[str, object]:
    run = deployment_service.deploy(
        project_id=str(payload["project_id"]),
        approved=bool(payload.get("approved", False)),
        dry_run=bool(payload.get("dry_run", True)),
    )
    return {"deployment_run_id": run.id, "status": run.status}


@router.get("/tools/list_artifacts/{project_id}")
def mcp_list_artifacts(project_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    artifacts = list(
        db.scalars(
            select(GeneratedArtifact)
            .where(GeneratedArtifact.project_id == project_id)
            .order_by(GeneratedArtifact.created_at.desc())
        )
    )
    return {
        "artifacts": [
            {"id": artifact.id, "name": artifact.name, "artifact_type": artifact.artifact_type, "path": artifact.path}
            for artifact in artifacts
        ]
    }


@router.get("/tools/get_generation_logs/{project_id}")
def mcp_get_generation_logs(project_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    runs = list(
        db.scalars(
            select(GenerationRun)
            .where(GenerationRun.project_id == project_id)
            .order_by(GenerationRun.started_at.desc())
        )
    )
    return {"generation_runs": [{"id": run.id, "status": run.status, "task_type": run.task_type} for run in runs]}


@router.get("/tools/get_test_results/{project_id}")
def mcp_get_test_results(project_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    runs = list(db.scalars(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.started_at.desc())))
    return {"test_runs": [{"id": run.id, "status": run.status, "passed": run.passed, "failed": run.failed} for run in runs]}


@router.get("/tools/get_deploy_status/{project_id}")
def mcp_get_deploy_status(project_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    runs = list(
        db.scalars(select(DeploymentRun).where(DeploymentRun.project_id == project_id).order_by(DeploymentRun.started_at.desc()))
    )
    return {"deployment_runs": [{"id": run.id, "status": run.status, "dry_run": run.dry_run} for run in runs]}


@router.post("/tools/{tool_name}/call")
def mcp_call_tool(
    tool_name: str,
    payload: dict[str, object],
    project_service: ProjectService = Depends(get_project_service),
    requirement_service: RequirementService = Depends(get_requirement_service),
    test_service: TestService = Depends(get_test_service),
    deployment_service: DeploymentService = Depends(get_deployment_service),
    registry: ProviderRegistry = Depends(get_provider_registry),
    correlation_id: str = Depends(get_correlation_id),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if tool_name == "create_project":
        return mcp_create_project(
            ProjectCreate(name=str(payload["name"]), description=str(payload.get("description", ""))),
            project_service,
        )
    if tool_name == "list_projects":
        return mcp_list_projects(project_service)
    if tool_name == "upload_requirements":
        return mcp_upload_requirements(payload={k: str(v) for k, v in payload.items()}, requirement_service=requirement_service)
    if tool_name == "structure_requirements":
        return mcp_structure_requirements(
            payload={k: str(v) for k, v in payload.items()},
            requirement_service=requirement_service,
            registry=registry,
            correlation_id=correlation_id,
        )
    if tool_name == "confirm_requirement_structure":
        return mcp_confirm_requirement_structure(payload=payload, requirement_service=requirement_service)
    if tool_name == "generate_code":
        from app.config.settings import get_settings
        from app.infrastructure.storage.artifact_storage import ArtifactStorage
        from app.services.generation import GenerationService

        generation_service = GenerationService(db, ArtifactStorage(get_settings()), project_service)
        run = generation_service.generate_code(
            project_id=str(payload["project_id"]),
            adapter=registry.get(),
            model=str(payload.get("model", "demo-code-v1")),
            correlation_id=correlation_id,
            approved=bool(payload.get("approved", False)),
        )
        return {"run_id": run.id, "status": run.status}
    if tool_name == "generate_tests":
        return mcp_generate_tests(payload=payload, test_service=test_service, registry=registry)
    if tool_name == "run_deploy":
        return mcp_run_deploy(payload=payload, deployment_service=deployment_service)
    if tool_name == "get_project_status":
        return mcp_get_project_status(str(payload["project_id"]), project_service)
    if tool_name == "list_artifacts":
        return mcp_list_artifacts(str(payload["project_id"]), db)
    if tool_name == "get_generation_logs":
        return mcp_get_generation_logs(str(payload["project_id"]), db)
    if tool_name == "get_test_results":
        return mcp_get_test_results(str(payload["project_id"]), db)
    if tool_name == "get_deploy_status":
        return mcp_get_deploy_status(str(payload["project_id"]), db)
    raise HTTPException(status_code=404, detail="MCP tool не поддерживается")


@router.post("/resources/read")
def mcp_read_resource(payload: dict[str, str], db: Session = Depends(get_db)) -> dict[str, object]:
    resource_uri = payload["resource_uri"]
    if not resource_uri.startswith("project://"):
        raise HTTPException(status_code=400, detail="Поддерживаются только project:// ресурсы")
    path = resource_uri.removeprefix("project://")
    project_id, _, resource_name = path.partition("/")
    if resource_name == "requirements/raw":
        document = db.scalar(
            select(RequirementDocument).where(RequirementDocument.project_id == project_id).order_by(RequirementDocument.version.desc())
        )
        return {"resource_uri": resource_uri, "content": document.content if document else None}
    if resource_name == "requirements/structured":
        structure = db.scalar(
            select(RequirementStructure).where(RequirementStructure.project_id == project_id).order_by(RequirementStructure.version.desc())
        )
        return {"resource_uri": resource_uri, "content": structure.structured_json if structure else None}
    if resource_name == "artifacts":
        return mcp_list_artifacts(project_id, db)
    if resource_name == "runs":
        return {
            "resource_uri": resource_uri,
            "content": {
                "generation_runs": mcp_get_generation_logs(project_id, db)["generation_runs"],
                "test_runs": mcp_get_test_results(project_id, db)["test_runs"],
                "deployment_runs": mcp_get_deploy_status(project_id, db)["deployment_runs"],
            },
        }
    if resource_name == "summary":
        try:
            summary = ProjectService(db).summary(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"resource_uri": resource_uri, "content": summary}
    raise HTTPException(status_code=404, detail="Ресурс не найден")


@router.post("/prompts/{prompt_name}")
def mcp_get_prompt_payload(prompt_name: str, payload: dict[str, object]) -> dict[str, object]:
    args = payload.get("args", {})
    prompts = {
        "analyze_requirements": "Проанализируй требования и подготовь структурированный JSON и Markdown.",
        "generate_backend_code": "Сгенерируй backend каркас FastAPI на основе подтверждённой структуры.",
        "generate_frontend_code": "Сгенерируй frontend каркас React/Vite на основе подтверждённой структуры.",
        "generate_tests": "Сгенерируй unit/API/smoke тесты и traceability matrix.",
        "review_architecture": "Проведи архитектурный review и выдели риски MVP.",
    }
    if prompt_name not in prompts:
        raise HTTPException(status_code=404, detail="Prompt не найден")
    return {"name": prompt_name, "prompt": prompts[prompt_name], "args": args}
