from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import AgentOrchestrator
from app.config.settings import Settings, get_settings
from app.db.models import ProviderConfig
from app.db.session import get_db as session_get_db
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.providers.registry import ProviderRegistry
from app.services.artifacts import ArtifactService
from app.services.audit import AuditService
from app.services.deployment import DeploymentService
from app.services.generation import GenerationService
from app.services.mcp_service import MCPService
from app.services.project_assistant import ProjectAssistantService
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.services.testing import TestService


def get_correlation_id(request: Request) -> str:
    return str(request.state.correlation_id)


def get_db() -> Generator[Session, None, None]:
    yield from session_get_db()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_storage(settings: Settings = Depends(get_settings)) -> ArtifactStorage:
    return ArtifactStorage(settings)


def get_requirement_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
    project_service: ProjectService = Depends(get_project_service),
) -> RequirementService:
    return RequirementService(db, storage, project_service)


def get_generation_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
    project_service: ProjectService = Depends(get_project_service),
) -> GenerationService:
    return GenerationService(db, storage, project_service)


def get_test_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
    project_service: ProjectService = Depends(get_project_service),
) -> TestService:
    return TestService(db, storage, project_service)


def get_deployment_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
    project_service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings),
) -> DeploymentService:
    return DeploymentService(db, storage, project_service, settings)


def get_provider_registry(settings: Settings = Depends(get_settings)) -> ProviderRegistry:
    return ProviderRegistry(settings)


def get_provider_registry_with_db(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProviderRegistry:
    configs = {
        item.provider: item
        for item in db.scalars(select(ProviderConfig)).all()
    }
    return ProviderRegistry(settings, configs)


def get_audit_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(db)


def get_artifact_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
) -> ArtifactService:
    return ArtifactService(db, storage)


def get_project_assistant_service(
    db: Session = Depends(get_db),
    storage: ArtifactStorage = Depends(get_storage),
    project_service: ProjectService = Depends(get_project_service),
) -> ProjectAssistantService:
    return ProjectAssistantService(db, storage, project_service)


def get_mcp_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    project_service: ProjectService = Depends(get_project_service),
    requirement_service: RequirementService = Depends(get_requirement_service),
) -> MCPService:
    return MCPService(db, settings, project_service, requirement_service)


def get_agent_orchestrator(db: Session = Depends(get_db)) -> AgentOrchestrator:
    return AgentOrchestrator(db)
