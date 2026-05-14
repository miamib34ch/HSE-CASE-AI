from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GeneratedArtifact, GenerationRun, RequirementStructure
from app.domain.enums.common import ArtifactType, ProjectStatus, RunStatus, TaskType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.providers.base import BaseLLMAdapter
from app.services.projects import ProjectService
from app.services.site_scaffold import (
    GeneratedFileEntry,
    build_site_files,
    build_site_spec,
    extract_generated_file_entries,
)
from app.utils.dates import utc_now


class GenerationService:
    def __init__(self, db: Session, storage: ArtifactStorage, project_service: ProjectService) -> None:
        self.db = db
        self.storage = storage
        self.project_service = project_service

    def _confirmed_structure(self, project_id: str) -> RequirementStructure:
        structure = self.db.scalar(
            select(RequirementStructure)
            .where(
                RequirementStructure.project_id == project_id,
                RequirementStructure.is_confirmed.is_(True),
            )
            .order_by(RequirementStructure.version.desc())
            .limit(1)
        )
        if structure is None:
            raise ValueError("Сначала подтвердите структуру требований")
        return structure

    def generate_code(
        self,
        *,
        project_id: str,
        adapter: BaseLLMAdapter,
        model: str,
        correlation_id: str,
        approved: bool,
        generation_mode: str = "auto",
    ) -> GenerationRun:
        if not approved:
            raise ValueError("Требуется подтверждение пользователя перед генерацией кода")
        structure = self._confirmed_structure(project_id)
        prompt = structure.markdown_content
        run = GenerationRun(
            project_id=project_id,
            provider=adapter.provider_name,
            model=model,
            task_type=TaskType.CODE_GENERATION.value,
            prompt_snapshot=prompt,
            input_payload={"structure_id": structure.id},
            output_payload={},
            status=RunStatus.RUNNING.value,
            correlation_id=correlation_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        llm_payload: dict[str, Any] | None = None
        result = None
        fallback_reason: str | None = None
        mode = generation_mode.lower()
        project = self.project_service.get_project(project_id)
        files: dict[str, GeneratedFileEntry]
        preview_url = ""
        site_spec_payload: dict[str, Any] | None = None
        if mode == "template":
            site_spec = build_site_spec(
                project_id=project_id,
                project_name=project.name,
                project_description=project.description,
                requirement_structure=cast(dict[str, Any], structure.structured_json),
                llm_payload=None,
            )
            files = self._text_entries(build_site_files(site_spec))
            site_spec_payload = site_spec.to_dict()
            preview_url = f"http://localhost:{site_spec.preview_port}"
        else:
            try:
                required_bundle_paths = ["docker-compose.generated.yml"]
                if adapter.provider_name == "fake" and mode == "llm":
                    result = adapter.generate_code(
                        prompt=self._llm_code_file_prompt(
                            prompt=prompt,
                            project_name=project.name,
                            project_description=project.description,
                        ),
                        model=model,
                    )
                    llm_files = self._entries_from_structured_output(result.structured_output.get("files"))
                else:
                    result = adapter.generate_code(
                        prompt=self._llm_code_file_prompt(
                            prompt=prompt,
                            project_name=project.name,
                            project_description=project.description,
                        ),
                        model=model,
                    )
                    llm_files = self._extract_or_repair_files(
                        adapter=adapter,
                        model=model,
                        raw_text=result.content,
                        required_paths=required_bundle_paths,
                        purpose="generated application files",
                    )
                if not llm_files:
                    raise ValueError("LLM не вернул files map в формате JSON")
                template_site_spec = build_site_spec(
                    project_id=project_id,
                    project_name=project.name,
                    project_description=project.description,
                    requirement_structure=cast(dict[str, Any], structure.structured_json),
                    llm_payload=None,
                )
                template_entries = self._text_entries(build_site_files(template_site_spec))
                llm_files = self._complete_or_fill_required_files(
                    adapter=adapter,
                    model=model,
                    files=dict(llm_files),
                    required_paths=required_bundle_paths,
                    prompt=self._llm_missing_files_prompt(
                        project_name=project.name,
                        project_description=project.description,
                        structure_markdown=prompt,
                    ),
                    template_files=template_entries,
                    strict=mode == "llm",
                )
                referenced_files = self._referenced_bundle_files(llm_files)
                llm_files = self._complete_or_fill_required_files(
                    adapter=adapter,
                    model=model,
                    files=dict(llm_files),
                    required_paths=referenced_files,
                    prompt=self._llm_missing_files_prompt(
                        project_name=project.name,
                        project_description=project.description,
                        structure_markdown=prompt,
                    ),
                    template_files=template_entries,
                    strict=mode == "llm",
                )
                llm_files = self._normalize_generated_compose_port(project_id=project_id, files=llm_files)
                self._validate_generated_site_files(llm_files)
                files = dict(llm_files)
                preview_url = self._preview_url_from_files(project_id, files)
            except Exception as exc:
                if mode == "llm":
                    raise ValueError(str(exc)) from exc
                fallback_reason = str(exc)
                site_spec = build_site_spec(
                    project_id=project_id,
                    project_name=project.name,
                    project_description=project.description,
                    requirement_structure=cast(dict[str, Any], structure.structured_json),
                    llm_payload=llm_payload,
                )
                files = self._text_entries(build_site_files(site_spec))
                site_spec_payload = site_spec.to_dict()
                preview_url = f"http://localhost:{site_spec.preview_port}"
        version_label = utc_now().strftime("%Y%m%d%H%M%S")
        snapshot_root = self.storage.snapshot_dir(project_id=project_id, area="generated", version_label=version_label)
        stored_files: list[tuple[str, Path]] = []
        for relative_name, entry in files.items():
            path = self._store_generated_entry(
                project_id=project_id,
                version_label=version_label,
                relative_name=relative_name,
                entry=entry,
            )
            stored_files.append((relative_name, path))
            self.db.add(
                GeneratedArtifact(
                    project_id=project_id,
                    generation_run_id=run.id,
                    artifact_type=ArtifactType.GENERATED_DOCS.value if relative_name.startswith("generated/") or relative_name == "README.md" else ArtifactType.GENERATED_CODE.value,
                    name=relative_name,
                    path=str(path),
                    version=1,
                    size_bytes=path.stat().st_size,
                )
            )
        run.output_payload = {
            "files": [name for name, _ in stored_files],
            "snapshot_root": str(snapshot_root),
            "preview_url": preview_url,
            "site_spec": site_spec_payload,
            "llm_spec_used": mode == "llm" or (mode == "auto" and fallback_reason is None and result is not None),
            "generation_mode": mode,
            "fallback_reason": fallback_reason,
        }
        if result is not None:
            run.tokens_in = result.tokens_in
            run.tokens_out = result.tokens_out
            run.cost_estimate = result.cost_estimate
        run.status = RunStatus.COMPLETED.value
        run.error_message = fallback_reason
        run.finished_at = utc_now()
        self.db.add(run)
        self.db.commit()
        self.project_service.update_status(project_id, ProjectStatus.CODE_GENERATED)
        return run

    def generate_schemas(
        self,
        *,
        project_id: str,
        adapter: BaseLLMAdapter,
        model: str,
        correlation_id: str,
        approved: bool,
        generation_mode: str = "auto",
    ) -> GenerationRun:
        if not approved:
            raise ValueError("Требуется подтверждение пользователя перед генерацией схем")
        structure = self._confirmed_structure(project_id)
        run = GenerationRun(
            project_id=project_id,
            provider=adapter.provider_name,
            model=model,
            task_type=TaskType.SCHEMA_GENERATION.value,
            prompt_snapshot=structure.markdown_content,
            input_payload={"structure_id": structure.id},
            output_payload={},
            status=RunStatus.RUNNING.value,
            correlation_id=correlation_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        structured_json = cast(dict[str, Any], structure.structured_json)
        mode = generation_mode.lower()
        fallback_reason: str | None = None
        files: dict[str, str]
        if mode == "template":
            files = self._build_template_schemas(structured_json)
        else:
            try:
                result = adapter.generate_text(
                    prompt=self._schema_generation_prompt(
                        project_name=self.project_service.get_project(project_id).name,
                        structure_markdown=structure.markdown_content,
                        structured_json=structured_json,
                    ),
                    model=model,
                )
                llm_files = self._extract_or_repair_files(
                    adapter=adapter,
                    model=model,
                    raw_text=result.content,
                    required_paths=["system_context.mmd", "domain_er.mmd", "module_map.mmd"],
                    purpose="mermaid diagrams",
                )
                if not llm_files:
                    raise ValueError("LLM не вернул JSON files map для схем")
                text_files = {
                    name: self._entry_text(entry)
                    for name, entry in llm_files.items()
                    if self._entry_text(entry).strip()
                }
                self._validate_diagram_files(text_files)
                files = text_files
            except Exception as exc:
                if mode == "llm":
                    raise ValueError(str(exc)) from exc
                fallback_reason = str(exc)
                files = self._build_template_schemas(structured_json)
        version_label = utc_now().strftime("%Y%m%d%H%M%S")
        for name, content in files.items():
            path = self.storage.write_versioned_text(
                project_id=project_id,
                area="generated",
                filename=name,
                content=content,
                version_label=version_label,
            )
            self.db.add(
                GeneratedArtifact(
                    project_id=project_id,
                    generation_run_id=run.id,
                    artifact_type=ArtifactType.GENERATED_DIAGRAM.value,
                    name=name,
                    path=str(path),
                    version=1,
                    size_bytes=path.stat().st_size,
                )
            )

        run.output_payload = {
            "files": list(files.keys()),
            "generation_mode": mode,
            "fallback_reason": fallback_reason,
        }
        run.status = RunStatus.COMPLETED.value
        run.error_message = fallback_reason
        run.finished_at = utc_now()
        self.db.add(run)
        self.db.commit()
        return run

    def _validate_generated_site_files(self, files: dict[str, GeneratedFileEntry]) -> None:
        required = {"docker-compose.generated.yml", *self._referenced_bundle_files(files)}
        missing = sorted(path for path in required if self._entry_text(files.get(path)).strip() == "")
        if missing:
            raise ValueError(f"LLM не вернул обязательные файлы: {', '.join(missing)}")
        if not self._has_user_facing_frontend(files):
            raise ValueError(
                "LLM вернул docker bundle без пользовательского интерфейса. Нужен frontend service или статический UI entrypoint."
            )

    def _preview_url_from_files(self, project_id: str, files: dict[str, GeneratedFileEntry]) -> str:
        compose_content = self._entry_text(files.get("docker-compose.generated.yml"))
        service_ports = self._compose_service_ports(compose_content)
        preferred_names = ("frontend", "web", "ui", "client", "site", "nginx")
        for service_name, host_port, _container_port in service_ports:
            if any(token in service_name.lower() for token in preferred_names):
                return f"http://localhost:{host_port}"
        for _service_name, host_port, container_port in service_ports:
            if container_port in {"80", "3000", "4173", "5173", "8080"}:
                return f"http://localhost:{host_port}"
        for _service_name, host_port, _container_port in service_ports:
            return f"http://localhost:{host_port}"
        site_spec = build_site_spec(
            project_id=project_id,
            project_name=self.project_service.get_project(project_id).name,
            project_description=self.project_service.get_project(project_id).description,
            requirement_structure={},
            llm_payload=None,
        )
        return f"http://localhost:{site_spec.preview_port}"

    def _normalize_generated_compose_port(
        self,
        *,
        project_id: str,
        files: dict[str, GeneratedFileEntry],
    ) -> dict[str, GeneratedFileEntry]:
        compose_path = "docker-compose.generated.yml"
        compose_content = self._entry_text(files.get(compose_path))
        if not compose_content.strip():
            return files
        safe_port = str(self._safe_preview_port(project_id))
        updated_lines: list[str] = []
        changed = False
        for line in compose_content.splitlines():
            stripped = line.strip().strip('"').strip("'")
            if ":" in stripped and "-" in stripped:
                host_port = stripped.split(":", 1)[0].split("-")[-1].strip().strip('"').strip("'")
                if host_port in {"8000", "8080", "5432", "6379"}:
                    container_port = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    line = line.replace(f'"{host_port}:{container_port}"', f'"{safe_port}:{container_port}"')
                    line = line.replace(f"'{host_port}:{container_port}'", f"'{safe_port}:{container_port}'")
                    line = line.replace(f"{host_port}:{container_port}", f"{safe_port}:{container_port}")
                    changed = True
            updated_lines.append(line)
        if changed:
            files[compose_path] = GeneratedFileEntry(
                text="\n".join(updated_lines) + ("\n" if compose_content.endswith("\n") else "")
            )
        return files

    def _safe_preview_port(self, project_id: str) -> int:
        site_spec = build_site_spec(
            project_id=project_id,
            project_name=self.project_service.get_project(project_id).name,
            project_description=self.project_service.get_project(project_id).description,
            requirement_structure={},
            llm_payload=None,
        )
        return site_spec.preview_port

    def _build_template_schemas(self, structured_json: dict[str, Any]) -> dict[str, str]:
        domain_entities = [str(item) for item in cast(list[Any], structured_json.get("domain_entities", []))]
        ui_screens = [str(item) for item in cast(list[Any], structured_json.get("ui_screens", []))]
        backend_modules = [str(item) for item in cast(list[Any], structured_json.get("backend_modules", []))]

        context_flow = "\n".join(
            [
                "flowchart TD",
                "  User[Пользователь] --> UI[React UI]",
                "  UI --> API[FastAPI Backend]",
                "  API --> DB[(PostgreSQL)]",
                "  API --> FS[(Artifact Storage)]",
                "  API --> Queue[(Redis/Celery)]",
            ]
        )

        er_lines = ["erDiagram"]
        for entity in domain_entities:
            entity_name = entity.upper().replace(" ", "_")
            er_lines.extend([f"  {entity_name} {{", "    string id", "    string name", "  }"])
        if "Project" in domain_entities and "Task" in domain_entities:
            er_lines.append("  PROJECT ||--o{ TASK : contains")
        if "Task" in domain_entities and "Comment" in domain_entities:
            er_lines.append("  TASK ||--o{ COMMENT : has")
        if "User" in domain_entities and "Task" in domain_entities:
            er_lines.append("  USER ||--o{ TASK : assigned_to")
        er_diagram = "\n".join(er_lines)

        mindmap = "\n".join(
            ["mindmap", "  root((CASE Platform))"]
            + [f"    Backend::{item}" for item in backend_modules]
            + [f"    UI::{item}" for item in ui_screens]
        )

        return {
            "system_context.mmd": context_flow,
            "domain_er.mmd": er_diagram,
            "module_map.mmd": mindmap,
        }

    def _schema_generation_prompt(
        self,
        *,
        project_name: str,
        structure_markdown: str,
        structured_json: dict[str, Any],
    ) -> str:
        return (
            "Сгенерируй только JSON без пояснений в формате "
            '{"files":{"system_context.mmd":"...", "domain_er.mmd":"...", "module_map.mmd":"..."}}. '
            "Значения файлов должны быть валидным Mermaid. "
            "Первая схема: system context/flowchart. Вторая: erDiagram по доменным сущностям. "
            "Третья: модульная карта или mindmap по backend/UI модулям. "
            f"\nПроект: {project_name}\n"
            f"\nПодтверждённая структура:\n{structure_markdown}\n"
            f"\nMachine-readable структура:\n{structured_json}\n"
        )

    def _validate_diagram_files(self, files: dict[str, str]) -> None:
        required = {"system_context.mmd", "domain_er.mmd", "module_map.mmd"}
        missing = sorted(path for path in required if path not in files)
        if missing:
            raise ValueError(f"LLM не вернул обязательные файлы схем: {', '.join(missing)}")

    def _extract_or_repair_files(
        self,
        *,
        adapter: BaseLLMAdapter,
        model: str,
        raw_text: str,
        required_paths: list[str],
        purpose: str,
    ) -> dict[str, GeneratedFileEntry] | None:
        parsed = extract_generated_file_entries(raw_text)
        if parsed:
            return parsed
        repair_result = adapter.generate_text(
            prompt=(
                "Преобразуй предыдущий ответ в строгий JSON без пояснений и без markdown. "
                "Формат строго: "
                '{"files":{"path":"content"}}. '
                f"Обязательные пути: {', '.join(required_paths)}. "
                f"Назначение набора файлов: {purpose}. "
                f"\nИсходный ответ модели:\n{raw_text}"
            ),
            model=model,
        )
        parsed_repair = extract_generated_file_entries(repair_result.content)
        if parsed_repair:
            return parsed_repair
        return self._entries_from_structured_output(repair_result.structured_output.get("files"))

    def _complete_or_fill_required_files(
        self,
        *,
        adapter: BaseLLMAdapter,
        model: str,
        files: dict[str, GeneratedFileEntry],
        required_paths: list[str],
        prompt: str,
        template_files: dict[str, GeneratedFileEntry],
        strict: bool,
    ) -> dict[str, GeneratedFileEntry]:
        missing = [path for path in required_paths if self._entry_text(files.get(path)).strip() == ""]
        if missing:
            completion_result = adapter.generate_text(prompt=prompt + f"\nНужны только эти пути: {missing}", model=model)
            repaired = extract_generated_file_entries(completion_result.content) or self._entries_from_structured_output(
                completion_result.structured_output.get("files")
            )
            if repaired:
                for path in missing:
                    content = repaired.get(path)
                    if content is not None and content.has_content:
                        files[path] = content
        remaining = [path for path in required_paths if self._entry_text(files.get(path)).strip() == ""]
        if remaining and not strict:
            for path in remaining:
                template_content = template_files.get(path)
                if template_content is not None and template_content.has_content:
                    files[path] = template_content
        return files

    def _llm_missing_files_prompt(
        self,
        *,
        project_name: str,
        project_description: str,
        structure_markdown: str,
    ) -> str:
        return (
            "Верни только JSON без пояснений в формате "
            '{"files":{"path":"content"}}. '
            "Нужно догенерировать только отсутствующие или пустые файлы docker bundle. "
            "Минимально обязателен docker-compose.generated.yml и все файлы, на которые он ссылается через build/dockerfile/env_file. "
            "Все значения должны быть полным содержимым файлов. "
            f"\nНазвание проекта: {project_name}\n"
            f"\nОписание проекта: {project_description}\n"
            f"\nПодтверждённая структура требований:\n{structure_markdown}\n"
        )

    def _site_generation_prompt(self, *, prompt: str, project_name: str) -> str:
        return (
            "Ты генерируешь спецификацию web-приложения для автоматической сборки реально полезного демонстрационного сайта. "
            "Верни только JSON без пояснений. "
            "Структура JSON: "
            '{"app_name":"...", "description":"...", "accent_color":"#hex", "hero_title":"...", "hero_subtitle":"...", '
            '"pages":["..."], "entities":[{"name":"...", "label":"...", "slug":"...", '
            '"fields":[{"name":"...", "label":"...", "type":"text"}], '
            '"records":[{"id":"...", "field":"value"}]}]}'
            "Сделай спецификацию максимально предметной для описанной системы. "
            "Если это заказ пиццы, должны появиться сущности типа Pizza/Menu/Cart/Order/Customer, экраны меню и корзины, а также демонстрационные записи. "
            f"\nНазвание проекта: {project_name}\n"
            "Подтверждённая структура требований:\n"
            f"{prompt}"
        )

    def _llm_code_file_prompt(
        self,
        *,
        prompt: str,
        project_name: str,
        project_description: str,
    ) -> str:
        return (
            "Сгенерируй только JSON без пояснений и markdown вокруг. "
            "Строго формат: "
            '{"files":{"docker-compose.generated.yml":"...", "path/to/other/file":"..."}}. '
            "Не добавляй текст до JSON и после JSON. "
            "Все значения должны быть полным содержимым файлов. "
            "Нельзя возвращать site spec, explanation, summary или markdown list. "
            "Нужно вернуть именно files map полного docker bundle. "
            "Обязательно: docker-compose.generated.yml должен быть самодостаточным и ссылаться только на файлы, которые ты тоже вернёшь в files map. "
            "Разрешены любые стеки для web app: Vue, React, Next.js, FastAPI, Node.js, Nginx, Postgres и т.д. "
            "Если в требованиях нужен frontend framework, обязательно верни и frontend файлы, а не только backend. "
            "Если используешь build.context и dockerfile, оба пути должны быть согласованы с файловой структурой в files map. "
            "Приложение должно запускаться через docker compose как полноценный web app, а не только API. "
            f"\nНазвание проекта: {project_name}\n"
            f"\nОписание проекта: {project_description}\n"
            f"\nПодтверждённая структура требований:\n{prompt}\n"
            "\nПример корректного начала ответа:\n"
            '{"files":{"docker-compose.generated.yml":"services:\\n  frontend:\\n    build:\\n      context: .\\n      dockerfile: ./frontend/Dockerfile\\n    ports:\\n      - \\"9171:80\\"\\n","frontend/Dockerfile":"FROM node:20-alpine\\n..."}}'
        )

    def _referenced_bundle_files(self, files: dict[str, GeneratedFileEntry]) -> list[str]:
        compose_content = self._entry_text(files.get("docker-compose.generated.yml"))
        referenced: set[str] = set()
        current_build_context: str | None = None
        for raw_line in compose_content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("build:"):
                build_value = line.split(":", 1)[1].strip().strip('"').strip("'")
                if build_value and not build_value.startswith("{"):
                    current_build_context = self._normalize_compose_path(build_value)
                    if current_build_context not in {"", "."}:
                        referenced.add(f"{current_build_context}/Dockerfile")
                    else:
                        referenced.add("Dockerfile")
            if line.startswith("context:"):
                current_build_context = self._normalize_compose_path(line.split(":", 1)[1].strip())
            if line.startswith("dockerfile:"):
                dockerfile_path = self._normalize_compose_path(line.split(":", 1)[1].strip())
                if dockerfile_path:
                    referenced.add(dockerfile_path)
            if line.startswith("env_file:"):
                current_build_context = current_build_context
            if line.startswith("-") and current_build_context is None:
                continue
        return sorted(referenced)

    def _entry_text(self, entry: GeneratedFileEntry | None) -> str:
        return "" if entry is None or entry.text is None else entry.text

    def _text_entries(self, files: dict[str, str]) -> dict[str, GeneratedFileEntry]:
        return {path: GeneratedFileEntry(text=content) for path, content in files.items()}

    def _entries_from_structured_output(self, payload: object) -> dict[str, GeneratedFileEntry] | None:
        if not isinstance(payload, dict):
            return None
        try:
            parsed = extract_generated_file_entries(json.dumps({"files": payload}, ensure_ascii=False))
        except TypeError:
            parsed = None
        return parsed

    def _store_generated_entry(
        self,
        *,
        project_id: str,
        version_label: str,
        relative_name: str,
        entry: GeneratedFileEntry,
    ) -> Path:
        if entry.binary is not None and Path(relative_name).suffix.lower() != ".svg":
            return self.storage.write_snapshot_bytes(
                project_id=project_id,
                area="generated",
                version_label=version_label,
                relative_path=relative_name,
                content=entry.binary,
            )
        return self.storage.write_snapshot_text(
            project_id=project_id,
            area="generated",
            version_label=version_label,
            relative_path=relative_name,
            content=entry.text or "",
        )

    def _has_user_facing_frontend(self, files: dict[str, GeneratedFileEntry]) -> bool:
        frontend_markers = (
            "frontend/",
            "client/",
            "ui/",
            "web/",
            "public/",
            "nginx/",
            "backend/app/static/",
        )
        frontend_filenames = {
            "index.html",
            "app.vue",
            "main.ts",
            "main.tsx",
            "main.js",
            "main.jsx",
            "vite.config.ts",
            "package.json",
        }
        for path, entry in files.items():
            normalized = path.lower()
            if self._entry_text(entry).strip() == "" and entry.binary is None:
                continue
            if normalized.startswith(frontend_markers):
                return True
            if Path(normalized).name in frontend_filenames and (
                normalized.startswith("frontend/")
                or normalized.startswith("client/")
                or normalized.startswith("ui/")
                or normalized.startswith("web/")
            ):
                return True
        compose_content = self._entry_text(files.get("docker-compose.generated.yml"))
        for service_name, _host_port, container_port in self._compose_service_ports(compose_content):
            if any(token in service_name.lower() for token in ("frontend", "web", "ui", "client", "site", "nginx")):
                return True
            if container_port in {"80", "3000", "4173", "5173", "8080"} and "api" not in service_name.lower():
                return True
        return False

    def _compose_service_ports(self, compose_content: str) -> list[tuple[str, str, str]]:
        service_ports: list[tuple[str, str, str]] = []
        in_services = False
        current_service: str | None = None
        in_ports = False
        for raw_line in compose_content.splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            stripped = raw_line.strip()
            if stripped == "services:":
                in_services = True
                current_service = None
                in_ports = False
                continue
            if in_services and indent == 2 and stripped.endswith(":"):
                current_service = stripped[:-1].strip()
                in_ports = False
                continue
            if in_services and current_service and indent == 4 and stripped == "ports:":
                in_ports = True
                continue
            if in_services and current_service and in_ports and indent >= 6 and stripped.startswith("-"):
                raw_mapping = stripped.lstrip("-").strip().strip('"').strip("'")
                if ":" not in raw_mapping:
                    continue
                host_port, container_port = raw_mapping.split(":", 1)
                host_port = host_port.strip()
                container_port = container_port.strip()
                if host_port.isdigit():
                    service_ports.append((current_service, host_port, container_port))
                continue
            if indent <= 4 and stripped.endswith(":") and stripped != "ports:":
                in_ports = False
        return service_ports

    def _normalize_compose_path(self, value: str) -> str:
        normalized = value.strip().strip('"').strip("'")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized == ".":
            return "."
        return normalized.strip("/")
