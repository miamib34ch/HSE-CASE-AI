from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from app.config.settings import Settings
from app.utils.dates import utc_now
from app.utils.files import safe_join, sanitize_filename


class ArtifactStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = Path(settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure_project_dirs(self, project_id: str) -> None:
        for suffix in [
            "requirements",
            "structured",
            "generated",
            "tests",
            "deployments",
            "exports",
        ]:
            safe_join(self.root, "projects", project_id, suffix).mkdir(parents=True, exist_ok=True)

    def write_versioned_text(
        self, project_id: str, area: str, filename: str, content: str, version_label: str | None = None
    ) -> Path:
        self.ensure_project_dirs(project_id)
        timestamp = version_label or utc_now().strftime("%Y%m%d%H%M%S")
        directory = safe_join(self.root, "projects", project_id, area, timestamp)
        directory.mkdir(parents=True, exist_ok=True)
        path = safe_join(directory, sanitize_filename(filename))
        path.write_text(content, encoding="utf-8")
        return path

    def write_versioned_bytes(
        self,
        project_id: str,
        area: str,
        filename: str,
        content: bytes,
        version_label: str | None = None,
    ) -> Path:
        self.ensure_project_dirs(project_id)
        timestamp = version_label or utc_now().strftime("%Y%m%d%H%M%S")
        directory = safe_join(self.root, "projects", project_id, area, timestamp)
        directory.mkdir(parents=True, exist_ok=True)
        path = safe_join(directory, sanitize_filename(filename))
        path.write_bytes(content)
        return path

    def snapshot_dir(self, project_id: str, area: str, version_label: str | None = None) -> Path:
        self.ensure_project_dirs(project_id)
        timestamp = version_label or utc_now().strftime("%Y%m%d%H%M%S")
        directory = safe_join(self.root, "projects", project_id, area, timestamp)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def write_snapshot_text(
        self,
        project_id: str,
        area: str,
        version_label: str,
        relative_path: str,
        content: str,
    ) -> Path:
        base_dir = self.snapshot_dir(project_id, area, version_label)
        parts = self._sanitize_relative_path(relative_path)
        path = safe_join(base_dir, *parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_snapshot_bytes(
        self,
        project_id: str,
        area: str,
        version_label: str,
        relative_path: str,
        content: bytes,
    ) -> Path:
        base_dir = self.snapshot_dir(project_id, area, version_label)
        parts = self._sanitize_relative_path(relative_path)
        path = safe_join(base_dir, *parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def export_project(self, project_id: str) -> Path:
        self.ensure_project_dirs(project_id)
        source_dir = safe_join(self.root, "projects", project_id)
        export_dir = safe_join(self.root, "projects", project_id, "exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        archive_path = safe_join(
            export_dir, f"project_export_{utc_now().strftime('%Y%m%d%H%M%S')}.zip"
        )
        with ZipFile(archive_path, "w") as archive:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, arcname=file_path.relative_to(source_dir))
        return archive_path

    def _sanitize_relative_path(self, relative_path: str) -> list[str]:
        sanitized_parts: list[str] = []
        for raw_part in Path(relative_path).parts:
            if raw_part in {"", ".", ".."}:
                continue
            sanitized_parts.append(sanitize_filename(raw_part))
        if not sanitized_parts:
            raise ValueError("Некорректный относительный путь для артефакта")
        return sanitized_parts
