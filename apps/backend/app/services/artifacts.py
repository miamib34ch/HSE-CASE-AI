from __future__ import annotations

import mimetypes
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import GeneratedArtifact
from app.domain.enums.common import ArtifactType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.utils.files import sanitize_filename

TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mmd",
    ".mermaid",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


class ArtifactService:
    def __init__(self, db: Session, storage: ArtifactStorage) -> None:
        self.db = db
        self.storage = storage

    def list_artifacts(self, project_id: str) -> list[GeneratedArtifact]:
        return list(
            self.db.scalars(
                select(GeneratedArtifact)
                .where(GeneratedArtifact.project_id == project_id)
                .order_by(GeneratedArtifact.created_at.desc())
            )
        )

    def get_artifact(self, project_id: str, artifact_id: str) -> GeneratedArtifact:
        artifact = self.db.get(GeneratedArtifact, artifact_id)
        if artifact is None or artifact.project_id != project_id:
            raise ValueError("Артефакт не найден")
        return artifact

    def is_text_artifact(self, artifact: GeneratedArtifact) -> bool:
        path = Path(artifact.path)
        mime_type, _ = mimetypes.guess_type(path.name)
        return path.suffix.lower() in TEXT_EXTENSIONS or bool(
            mime_type and mime_type.startswith("text/")
        )

    def is_image_artifact(self, artifact: GeneratedArtifact) -> bool:
        mime_type, _ = mimetypes.guess_type(Path(artifact.path).name)
        return bool(mime_type and mime_type.startswith("image/"))

    def read_text_content(self, artifact: GeneratedArtifact) -> str | None:
        if not self.is_text_artifact(artifact):
            return None
        path = Path(artifact.path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="replace")

    def upload_bytes(
        self,
        *,
        project_id: str,
        filename: str,
        content: bytes,
        artifact_type: ArtifactType = ArtifactType.MANUAL_UPLOAD,
    ) -> GeneratedArtifact:
        version = self._next_version(project_id, filename)
        path = self.storage.write_versioned_bytes(
            project_id=project_id,
            area="generated",
            filename=filename,
            content=content,
        )
        artifact = GeneratedArtifact(
            project_id=project_id,
            artifact_type=artifact_type.value,
            name=sanitize_filename(filename),
            path=str(path),
            version=version,
            size_bytes=len(content),
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def update_text_artifact(
        self,
        *,
        project_id: str,
        artifact_id: str,
        content: str,
    ) -> GeneratedArtifact:
        artifact = self.get_artifact(project_id, artifact_id)
        if not self.is_text_artifact(artifact):
            raise ValueError("Редактирование доступно только для текстовых артефактов")
        artifact_type = ArtifactType(artifact.artifact_type)
        return self.upload_bytes(
            project_id=project_id,
            filename=artifact.name,
            content=content.encode("utf-8"),
            artifact_type=artifact_type,
        )

    def delete_artifact(self, project_id: str, artifact_id: str) -> bool:
        artifact = self.db.get(GeneratedArtifact, artifact_id)
        if artifact is None or artifact.project_id != project_id:
            return False
        path = Path(artifact.path)
        try:
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
            self.db.delete(artifact)
            self.db.commit()
            return True
        except OSError as exc:
            self.db.rollback()
            raise ValueError(f"Не удалось удалить файл артефакта: {exc}") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ValueError(f"Не удалось удалить запись артефакта из БД: {exc}") from exc

    def _next_version(self, project_id: str, filename: str) -> int:
        version = self.db.scalar(
            select(func.max(GeneratedArtifact.version)).where(
                GeneratedArtifact.project_id == project_id,
                GeneratedArtifact.name == sanitize_filename(filename),
            )
        )
        return int(version or 0) + 1
