from pathlib import Path

from app.config.settings import get_settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.infrastructure.storage.artifact_storage import ArtifactStorage


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    storage = ArtifactStorage(settings)
    project_service = ProjectService(db)
    requirement_service = RequirementService(db, storage, project_service)
    project = project_service.create_project(
        name="Demo TaskFlow Platform",
        description="Сидовые данные для демонстрации CASE pipeline",
    )
    content = Path("examples/demo_requirements.md").read_text(encoding="utf-8")
    requirement_service.upload(
        project_id=project.id,
        content=content,
        source_type="markdown",
        filename="demo_requirements.md",
    )
    print(f"Created demo project: {project.id}")
    db.close()


if __name__ == "__main__":
    main()

