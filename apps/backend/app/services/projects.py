from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import GeneratedArtifact, GenerationRun, Project, RequirementStructure, TestRun
from app.domain.enums.common import ProjectStatus


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, *, name: str, description: str) -> Project:
        project = Project(name=name, description=description, status=ProjectStatus.DRAFT.value)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self) -> list[Project]:
        return list(self.db.scalars(select(Project).order_by(Project.created_at.desc())))

    def get_project(self, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise ValueError("Проект не найден")
        return project

    def update_status(self, project_id: str, status: ProjectStatus) -> Project:
        project = self.get_project(project_id)
        project.status = status.value
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def summary(self, project_id: str) -> dict[str, object]:
        project = self.get_project(project_id)
        counts = {
            "artifacts": self.db.scalar(select(func.count()).select_from(GeneratedArtifact).where(GeneratedArtifact.project_id == project_id)) or 0,
            "generation_runs": self.db.scalar(select(func.count()).select_from(GenerationRun).where(GenerationRun.project_id == project_id)) or 0,
            "test_runs": self.db.scalar(select(func.count()).select_from(TestRun).where(TestRun.project_id == project_id)) or 0,
            "structures": self.db.scalar(select(func.count()).select_from(RequirementStructure).where(RequirementStructure.project_id == project_id)) or 0,
        }
        return {"project_id": project.id, "status": project.status, "counts": counts, "last_updated_at": project.updated_at}

