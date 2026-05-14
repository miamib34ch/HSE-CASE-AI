from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    DeploymentRun,
    GeneratedArtifact,
    GenerationRun,
    RequirementDocument,
    RequirementStructure,
    TestRun,
)
from app.domain.enums.common import ArtifactType, TaskType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.providers.base import BaseLLMAdapter
from app.services.projects import ProjectService
from app.services.site_scaffold import build_site_files, build_site_spec, extract_site_spec_json


@dataclass(slots=True)
class AssistantChange:
    path: str
    reason: str
    content: str


@dataclass(slots=True)
class AssistantContextEntry:
    name: str
    source_type: str
    included: bool
    note: str | None = None


@dataclass(slots=True)
class AssistantResult:
    reply: str
    used_provider: str
    used_model: str
    applied_paths: list[str]
    suggested_paths: list[str]
    fallback_reason: str | None
    changes: list[AssistantChange]
    context_items: list[AssistantContextEntry]


TEXT_EXTENSIONS = {
    ".css",
    ".env",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mmd",
    ".mermaid",
    ".py",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
}


class ProjectAssistantService:
    def __init__(
        self,
        db: Session,
        storage: ArtifactStorage,
        project_service: ProjectService,
    ) -> None:
        self.db = db
        self.storage = storage
        self.project_service = project_service

    def chat(
        self,
        *,
        project_id: str,
        message: str,
        adapter: BaseLLMAdapter,
        model: str,
        apply_changes: bool,
        approved: bool,
    ) -> AssistantResult:
        project = self.project_service.get_project(project_id)
        generation_run = self._latest_code_generation(project_id)
        snapshot_root = Path(str(dict(generation_run.output_payload).get("snapshot_root", "")))
        if not snapshot_root.exists():
            raise ValueError("Snapshot сгенерированного проекта не найден")
        deploy_run = self._latest_deploy_run(project_id)
        context_payload, context_items = self._build_project_context(project_id=project_id, snapshot_root=snapshot_root)
        changes: list[AssistantChange] = []
        reply = ""
        fallback_reason: str | None = None

        if adapter.provider_name != "fake" and adapter.is_available():
            try:
                llm_result = adapter.generate_text(
                    prompt=self._assistant_prompt(
                        project_name=project.name,
                        project_description=project.description,
                        user_message=message,
                        deploy_logs=deploy_run.logs if deploy_run is not None else "",
                        context_payload=context_payload,
                    ),
                    model=model,
                )
                parsed = extract_site_spec_json(llm_result.content) or {}
                reply = str(parsed.get("reply", "")).strip()
                changes = self._parse_changes(parsed.get("changes"))
                if not reply:
                    raise ValueError("LLM не вернула текст ответа помощника")
            except Exception as exc:
                fallback_reason = str(exc)
                reply, changes = self._heuristic_response(
                    project_id=project_id,
                    user_message=message,
                    deploy_logs=deploy_run.logs if deploy_run is not None else "",
                    snapshot_root=snapshot_root,
                )
        else:
            reply, changes = self._heuristic_response(
                project_id=project_id,
                user_message=message,
                deploy_logs=deploy_run.logs if deploy_run is not None else "",
                snapshot_root=snapshot_root,
            )

        applied_paths: list[str] = []
        if apply_changes:
            if not approved:
                raise ValueError("Для применения правок через помощника требуется подтверждение пользователя")
            applied_paths = self._apply_changes(
                project_id=project_id,
                generation_run_id=generation_run.id,
                snapshot_root=snapshot_root,
                changes=changes,
            )

        return AssistantResult(
            reply=reply,
            used_provider=adapter.provider_name,
            used_model=model,
            applied_paths=applied_paths,
            suggested_paths=[change.path for change in changes],
            fallback_reason=fallback_reason,
            changes=changes,
            context_items=context_items,
        )

    def _latest_code_generation(self, project_id: str) -> GenerationRun:
        run = self.db.scalar(
            select(GenerationRun)
            .where(
                GenerationRun.project_id == project_id,
                GenerationRun.task_type == TaskType.CODE_GENERATION.value,
            )
            .order_by(GenerationRun.started_at.desc())
            .limit(1)
        )
        if run is None:
            raise ValueError("Сначала выполните генерацию кода")
        return run

    def _latest_deploy_run(self, project_id: str) -> DeploymentRun | None:
        return self.db.scalar(
            select(DeploymentRun)
            .where(DeploymentRun.project_id == project_id)
            .order_by(DeploymentRun.started_at.desc())
            .limit(1)
        )

    def _assistant_prompt(
        self,
        *,
        project_name: str,
        project_description: str,
        user_message: str,
        deploy_logs: str,
        context_payload: str,
    ) -> str:
        return (
            "Ты технический помощник по уже сгенерированному проекту. "
            "Нужно проанализировать сообщение пользователя, последние deploy logs, requirements, артефакты и текущие файлы snapshot. "
            "Верни только JSON без пояснений в формате "
            '{"reply":"...", "changes":[{"path":"backend/Dockerfile","reason":"...","content":"..."}]}. '
            "Если правки не нужны, верни пустой массив changes. "
            "Правки должны быть минимальными и точечными. "
            "Если проблема в deploy, исправляй связанные docker/config/runtime файлы. "
            f"\nНазвание проекта: {project_name}\n"
            f"\nОписание проекта: {project_description}\n"
            f"\nСообщение пользователя:\n{user_message}\n"
            f"\nПоследние логи deploy:\n{deploy_logs}\n"
            f"\nКонтекст проекта:\n{context_payload}\n"
        )

    def _parse_changes(self, raw_changes: Any) -> list[AssistantChange]:
        if not isinstance(raw_changes, list):
            return []
        changes: list[AssistantChange] = []
        for item in raw_changes:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", ""))
            reason = str(item.get("reason", "")).strip() or "Правка от помощника"
            if path and content:
                changes.append(AssistantChange(path=path, reason=reason, content=content))
        return changes

    def _heuristic_response(
        self,
        *,
        project_id: str,
        user_message: str,
        deploy_logs: str,
        snapshot_root: Path,
    ) -> tuple[str, list[AssistantChange]]:
        message = f"{user_message}\n{deploy_logs}".lower()
        changes: list[AssistantChange] = []
        reply = "Помощник проанализировал проект и не нашёл безопасных автоматических правок."

        dockerfile_path = snapshot_root / "backend" / "Dockerfile"
        requirements_path = snapshot_root / "backend" / "requirements.txt"
        compose_path = snapshot_root / "docker-compose.generated.yml"

        if dockerfile_path.exists() and requirements_path.exists():
            dockerfile_content = dockerfile_path.read_text(encoding="utf-8", errors="replace")
            if "copy requirements.txt ." in dockerfile_content.lower() or 'copy "requirements.txt"' in dockerfile_content.lower():
                patched = dockerfile_content.replace("COPY requirements.txt .", "COPY backend/requirements.txt ./requirements.txt")
                patched = patched.replace("COPY requirements.txt ./", "COPY backend/requirements.txt ./requirements.txt")
                if patched != dockerfile_content:
                    changes.append(
                        AssistantChange(
                            path="backend/Dockerfile",
                            reason="Исправлен путь COPY requirements.txt относительно build context",
                            content=patched,
                        )
                    )
                    reply = "Найдена типовая ошибка Dockerfile: `requirements.txt` копировался из неверного пути. Предлагаю исправить `COPY` относительно корня compose context."

        if compose_path.exists():
            compose_content = compose_path.read_text(encoding="utf-8", errors="replace")
            preview_port = self._safe_preview_port(project_id)
            if "8000:8000" in compose_content:
                patched_compose = compose_content.replace("8000:8000", f"{preview_port}:8000")
                changes.append(
                    AssistantChange(
                        path="docker-compose.generated.yml",
                        reason="Устранён конфликт host-port с backend CASE-платформы",
                        content=patched_compose,
                    )
                )
                reply = "Найдён конфликт портов: generated app пыталась занять `8000`, который уже использует backend платформы. Предлагаю перенести её на отдельный preview-порт."

        if not changes and ("requirements.txt" in message or "copy requirements.txt" in message):
            template_files = self._template_files(project_id)
            content = template_files.get("backend/Dockerfile", "")
            if content:
                changes.append(
                    AssistantChange(
                        path="backend/Dockerfile",
                        reason="Подставлен безопасный template Dockerfile",
                        content=content,
                    )
                )
                reply = "Логи деплоя указывают на проблему с Dockerfile. Предлагаю заменить его на безопасный шаблонный вариант, совместимый с текущим snapshot."

        return reply, changes

    def _build_project_context(
        self,
        *,
        project_id: str,
        snapshot_root: Path,
    ) -> tuple[str, list[AssistantContextEntry]]:
        context_parts: list[str] = []
        context_items: list[AssistantContextEntry] = []
        total_chars = 0
        max_total_chars = 120_000
        max_file_chars = 12_000

        latest_requirement = self.db.scalar(
            select(RequirementDocument)
            .where(RequirementDocument.project_id == project_id)
            .order_by(RequirementDocument.version.desc())
            .limit(1)
        )
        if latest_requirement is not None:
            content = latest_requirement.content[:max_file_chars]
            context_parts.append(f"[latest_requirement_document]\n{content}")
            total_chars += len(content)
            context_items.append(
                AssistantContextEntry(
                    name=latest_requirement.filename,
                    source_type="requirement_document",
                    included=True,
                    note="Последняя версия исходных требований",
                )
            )

        latest_structure = self.db.scalar(
            select(RequirementStructure)
            .where(RequirementStructure.project_id == project_id)
            .order_by(RequirementStructure.version.desc())
            .limit(1)
        )
        if latest_structure is not None:
            content = latest_structure.markdown_content[:max_file_chars]
            context_parts.append(f"[latest_requirement_structure]\n{content}")
            total_chars += len(content)
            context_items.append(
                AssistantContextEntry(
                    name=f"requirement_structure_v{latest_structure.version}",
                    source_type="requirement_structure",
                    included=True,
                    note="Последняя структурированная версия требований",
                )
            )

        recent_generation_runs = list(
            self.db.scalars(
                select(GenerationRun)
                .where(GenerationRun.project_id == project_id)
                .order_by(GenerationRun.started_at.desc())
                .limit(5)
            )
        )
        if recent_generation_runs:
            generation_summary: list[dict[str, object]] = [
                {
                    "id": run.id,
                    "task_type": run.task_type,
                    "status": run.status,
                    "provider": run.provider,
                    "model": run.model,
                    "error_message": run.error_message,
                }
                for run in recent_generation_runs
            ]
            rendered = str(generation_summary)
            context_parts.append(f"[recent_generation_runs]\n{rendered}")
            total_chars += len(rendered)
            context_items.append(
                AssistantContextEntry(
                    name="recent_generation_runs",
                    source_type="generation_runs",
                    included=True,
                    note="Последние 5 generation runs",
                )
            )

        recent_test_runs = list(
            self.db.scalars(
                select(TestRun)
                .where(TestRun.project_id == project_id)
                .order_by(TestRun.started_at.desc())
                .limit(3)
            )
        )
        if recent_test_runs:
            test_summary: list[dict[str, object]] = [
                {
                    "id": run.id,
                    "status": run.status,
                    "passed": run.passed,
                    "failed": run.failed,
                    "coverage_summary": run.coverage_summary,
                }
                for run in recent_test_runs
            ]
            rendered = str(test_summary)
            context_parts.append(f"[recent_test_runs]\n{rendered}")
            total_chars += len(rendered)
            context_items.append(
                AssistantContextEntry(
                    name="recent_test_runs",
                    source_type="test_runs",
                    included=True,
                    note="Последние 3 test runs",
                )
            )

        recent_deploy_runs = list(
            self.db.scalars(
                select(DeploymentRun)
                .where(DeploymentRun.project_id == project_id)
                .order_by(DeploymentRun.started_at.desc())
                .limit(3)
            )
        )
        if recent_deploy_runs:
            deploy_summary = cast(
                list[dict[str, object]],
                [
                    {
                        "id": run.id,
                        "status": run.status,
                        "dry_run": run.dry_run,
                        "logs_excerpt": run.logs[:2000],
                    }
                    for run in recent_deploy_runs
                ],
            )
            rendered = str(deploy_summary)
            context_parts.append(f"[recent_deploy_runs]\n{rendered}")
            total_chars += len(rendered)
            context_items.append(
                AssistantContextEntry(
                    name="recent_deploy_runs",
                    source_type="deploy_runs",
                    included=True,
                    note="Последние 3 deploy runs",
                )
            )

        artifacts = list(
            self.db.scalars(
                select(GeneratedArtifact)
                .where(GeneratedArtifact.project_id == project_id)
                .order_by(GeneratedArtifact.created_at.desc())
            )
        )
        for artifact in artifacts:
            path = Path(artifact.path)
            is_text = self._is_text_artifact(path)
            if not is_text:
                context_items.append(
                    AssistantContextEntry(
                        name=artifact.name,
                        source_type=artifact.artifact_type,
                        included=False,
                        note="Бинарный или неподдерживаемый для inline-контекста артефакт",
                    )
                )
                continue
            if total_chars >= max_total_chars:
                context_items.append(
                    AssistantContextEntry(
                        name=artifact.name,
                        source_type=artifact.artifact_type,
                        included=False,
                        note="Пропущен из-за лимита общего контекста",
                    )
                )
                continue
            if not path.exists() or not path.is_file():
                context_items.append(
                    AssistantContextEntry(
                        name=artifact.name,
                        source_type=artifact.artifact_type,
                        included=False,
                        note="Файл артефакта отсутствует на диске",
                    )
                )
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            excerpt = content[:max_file_chars]
            total_chars += len(excerpt)
            context_parts.append(f"[artifact:{artifact.name}]\n{excerpt}")
            note = None
            if len(content) > max_file_chars:
                note = "Контент обрезан по лимиту размера"
            context_items.append(
                AssistantContextEntry(
                    name=artifact.name,
                    source_type=artifact.artifact_type,
                    included=True,
                    note=note,
                )
            )

        if snapshot_root.exists():
            context_items.append(
                AssistantContextEntry(
                    name=str(snapshot_root),
                    source_type="snapshot_root",
                    included=True,
                    note="Корневой каталог текущего generated snapshot",
                )
            )

        return "\n\n".join(context_parts), context_items

    def _apply_changes(
        self,
        *,
        project_id: str,
        generation_run_id: str,
        snapshot_root: Path,
        changes: list[AssistantChange],
    ) -> list[str]:
        if not changes:
            return []
        version_label = snapshot_root.name
        applied_paths: list[str] = []
        for change in changes:
            path = self.storage.write_snapshot_text(
                project_id=project_id,
                area="generated",
                version_label=version_label,
                relative_path=change.path,
                content=change.content,
            )
            self.db.add(
                GeneratedArtifact(
                    project_id=project_id,
                    generation_run_id=generation_run_id,
                    artifact_type=self._artifact_type_for_path(change.path),
                    name=change.path,
                    path=str(path),
                    version=self._next_artifact_version(project_id, change.path),
                    size_bytes=path.stat().st_size,
                )
            )
            applied_paths.append(change.path)
        self.db.commit()
        return applied_paths

    def _next_artifact_version(self, project_id: str, name: str) -> int:
        version = self.db.scalar(
            select(func.max(GeneratedArtifact.version)).where(
                GeneratedArtifact.project_id == project_id,
                GeneratedArtifact.name == name,
            )
        )
        return int(version or 0) + 1

    def _artifact_type_for_path(self, path: str) -> str:
        if path.startswith("generated/") or path == "README.md":
            return ArtifactType.GENERATED_DOCS.value
        if path.endswith(".mmd") or path.endswith(".mermaid"):
            return ArtifactType.GENERATED_DIAGRAM.value
        if "test" in path.lower() or path.endswith(".xml"):
            return ArtifactType.GENERATED_TESTS.value
        if path.endswith(".yml") or path.endswith(".yaml"):
            return ArtifactType.DEPLOYMENT_BUNDLE.value
        return ArtifactType.GENERATED_CODE.value

    def _template_files(self, project_id: str) -> dict[str, str]:
        project = self.project_service.get_project(project_id)
        structure = self.db.scalar(
            select(RequirementStructure)
            .where(
                RequirementStructure.project_id == project_id,
                RequirementStructure.is_confirmed.is_(True),
            )
            .order_by(RequirementStructure.version.desc())
            .limit(1)
        )
        requirement_structure = cast(dict[str, Any], structure.structured_json) if structure is not None else {}
        site_spec = build_site_spec(
            project_id=project_id,
            project_name=project.name,
            project_description=project.description,
            requirement_structure=requirement_structure,
            llm_payload=None,
        )
        return build_site_files(site_spec)

    def _safe_preview_port(self, project_id: str) -> int:
        generation_run = self._latest_code_generation(project_id)
        preview_url = str(dict(generation_run.output_payload).get("preview_url", ""))
        parsed = urlparse(preview_url)
        if parsed.port is not None:
            return parsed.port
        template_files = self._template_files(project_id)
        compose_content = template_files.get("docker-compose.generated.yml", "")
        for line in compose_content.splitlines():
            if ":8000" in line and "-" in line:
                host_port = line.split(":8000", 1)[0].split("-")[-1].strip().strip('"').strip("'")
                if host_port.isdigit():
                    return int(host_port)
        return 9199

    def _is_text_artifact(self, path: Path) -> bool:
        mime_type, _ = mimetypes.guess_type(path.name)
        return path.suffix.lower() in TEXT_EXTENSIONS or bool(mime_type and mime_type.startswith("text/"))
