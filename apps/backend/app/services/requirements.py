from __future__ import annotations

import json
from textwrap import dedent
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    GeneratedArtifact,
    GenerationRun,
    RequirementDocument,
    RequirementStructure,
)
from app.domain.enums.common import ArtifactType, ProjectStatus, RunStatus, TaskType
from app.infrastructure.storage.artifact_storage import ArtifactStorage
from app.providers.base import BaseLLMAdapter
from app.providers.fake import FakeLLMAdapter
from app.services.projects import ProjectService
from app.services.site_scaffold import extract_site_spec_json


class RequirementService:
    def __init__(self, db: Session, storage: ArtifactStorage, project_service: ProjectService) -> None:
        self.db = db
        self.storage = storage
        self.project_service = project_service

    def upload(self, *, project_id: str, content: str, source_type: str, filename: str) -> RequirementDocument:
        current_version = (
            self.db.scalar(
                select(RequirementDocument.version)
                .where(RequirementDocument.project_id == project_id)
                .order_by(RequirementDocument.version.desc())
                .limit(1)
            )
            or 0
        )
        document = RequirementDocument(
            project_id=project_id,
            content=content,
            source_type=source_type,
            filename=filename,
            version=current_version + 1,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        path = self.storage.write_versioned_text(project_id, "requirements", filename, content)
        artifact = GeneratedArtifact(
            project_id=project_id,
            artifact_type=ArtifactType.RAW_REQUIREMENTS.value,
            name=filename,
            path=str(path),
            version=document.version,
            size_bytes=len(content.encode("utf-8")),
        )
        self.db.add(artifact)
        self.db.commit()
        self.project_service.update_status(project_id, ProjectStatus.REQUIREMENTS_UPLOADED)
        return document

    def draft_from_description(
        self,
        *,
        project_id: str,
        description: str,
        adapter: BaseLLMAdapter,
        model: str,
        correlation_id: str,
        auto_structure: bool,
        generation_mode: str = "auto",
    ) -> tuple[RequirementDocument, RequirementStructure | None]:
        markdown = self._draft_requirements_markdown(
            description=description,
            adapter=adapter,
            model=model,
            generation_mode=generation_mode,
        )
        document = self.upload(
            project_id=project_id,
            content=markdown,
            source_type="generated_from_description",
            filename="requirements.generated.md",
        )
        structure = None
        if auto_structure:
            structure = self.structure(
                project_id=project_id,
                adapter=adapter,
                model=model,
                correlation_id=correlation_id,
                generation_mode=generation_mode,
            )
        return document, structure

    def latest_document(self, project_id: str) -> RequirementDocument:
        document = self.db.scalar(
            select(RequirementDocument)
            .where(RequirementDocument.project_id == project_id)
            .order_by(RequirementDocument.version.desc())
            .limit(1)
        )
        if document is None:
            raise ValueError("Требования ещё не загружены")
        return document

    def latest_structure(self, project_id: str) -> RequirementStructure | None:
        return self.db.scalar(
            select(RequirementStructure)
            .where(RequirementStructure.project_id == project_id)
            .order_by(RequirementStructure.version.desc())
            .limit(1)
        )

    def structure(
        self,
        *,
        project_id: str,
        adapter: BaseLLMAdapter,
        model: str,
        correlation_id: str,
        generation_mode: str = "auto",
    ) -> RequirementStructure:
        document = self.latest_document(project_id)
        latest_structure = self.latest_structure(project_id)
        run = GenerationRun(
            project_id=project_id,
            provider=adapter.provider_name,
            model=model,
            task_type=TaskType.REQUIREMENTS_ANALYSIS.value,
            prompt_snapshot=document.content,
            input_payload={"document_id": document.id, "source_type": document.source_type},
            output_payload={},
            status=RunStatus.RUNNING.value,
            correlation_id=correlation_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        fallback_reason: str | None = None
        mode = generation_mode.lower()
        use_llm = mode == "llm" or (mode == "auto" and adapter.provider_name != "fake" and adapter.is_available())
        try:
            if use_llm:
                result = adapter.generate_text(
                    prompt=self._analysis_prompt(document.content),
                    model=model,
                )
                parsed = extract_site_spec_json(result.content)
                structured_payload = self._normalize_structure_payload(parsed, document.content)
                markdown_content = self._render_structure_markdown(structured_payload)
            else:
                structured_adapter: BaseLLMAdapter = FakeLLMAdapter() if mode == "template" else adapter
                structured_model = "demo-analysis-v1" if mode == "template" else model
                result = structured_adapter.generate_structured(
                    prompt=document.content,
                    model=structured_model,
                    schema_name="RequirementStructure",
                )
                structured_payload = result.structured_output
                markdown_content = result.content
        except Exception as exc:
            if mode == "llm":
                raise ValueError(str(exc)) from exc
            fallback_reason = str(exc)
            fallback_adapter = FakeLLMAdapter()
            result = fallback_adapter.generate_structured(
                prompt=document.content,
                model="demo-analysis-v1",
                schema_name="RequirementStructure",
            )
            structured_payload = result.structured_output
            markdown_content = result.content
        version = (latest_structure.version if latest_structure else 0) + 1
        structure = RequirementStructure(
            project_id=project_id,
            requirement_document_id=document.id,
            version=version,
            structured_json=structured_payload,
            markdown_content=markdown_content,
            is_confirmed=False,
        )
        self.db.add(structure)
        run.output_payload = {
            "structure_id": structure.id,
            "preview": markdown_content,
            "fallback_reason": fallback_reason,
        }
        run.status = RunStatus.COMPLETED.value
        run.error_message = fallback_reason
        run.tokens_in = result.tokens_in
        run.tokens_out = result.tokens_out
        run.cost_estimate = result.cost_estimate
        self.db.add(run)
        self.db.commit()
        self.db.refresh(structure)
        json_path = self.storage.write_versioned_text(
            project_id, "structured", f"structure_v{version}.json", json.dumps(structure.structured_json, ensure_ascii=False, indent=2)
        )
        md_path = self.storage.write_versioned_text(
            project_id, "structured", f"structure_v{version}.md", structure.markdown_content
        )
        self.db.add_all(
            [
                GeneratedArtifact(
                    project_id=project_id,
                    generation_run_id=run.id,
                    artifact_type=ArtifactType.STRUCTURED_REQUIREMENTS_JSON.value,
                    name=json_path.name,
                    path=str(json_path),
                    version=version,
                    size_bytes=json_path.stat().st_size,
                ),
                GeneratedArtifact(
                    project_id=project_id,
                    generation_run_id=run.id,
                    artifact_type=ArtifactType.STRUCTURED_REQUIREMENTS_MARKDOWN.value,
                    name=md_path.name,
                    path=str(md_path),
                    version=version,
                    size_bytes=md_path.stat().st_size,
                ),
            ]
        )
        self.db.commit()
        self.project_service.update_status(project_id, ProjectStatus.REQUIREMENTS_STRUCTURED)
        return structure

    def confirm(
        self,
        *,
        project_id: str,
        approved: bool,
        markdown_content: str | None,
        structured_json: dict[str, object] | None,
    ) -> RequirementStructure:
        if not approved:
            raise ValueError("Для подтверждения структуры требуется approved=true")
        structure = self.latest_structure(project_id)
        if structure is None:
            raise ValueError("Структура требований ещё не создана")
        if markdown_content is not None:
            structure.markdown_content = markdown_content
        if structured_json is not None:
            structure.structured_json = structured_json
        structure.is_confirmed = True
        self.db.add(structure)
        self.db.commit()
        self.db.refresh(structure)
        self.project_service.update_status(project_id, ProjectStatus.REQUIREMENTS_CONFIRMED)
        return structure

    def _analysis_prompt(self, document_content: str) -> str:
        return (
            "Проанализируй требования и верни только JSON без комментариев. "
            "Нужны ключи: functional_requirements, non_functional_requirements, domain_entities, "
            "user_stories, acceptance_criteria, constraints, ui_screens, backend_modules, "
            "test_scenarios, risks, gaps_and_conflicts, system_name. "
            "Все значения кроме system_name должны быть массивами строк. "
            "Если речь идёт о food delivery, pizza ordering, ecommerce или каталоге товаров, "
            "не используй абстрактные Project/Task/Comment, а выделяй реальные доменные сущности вроде Pizza, Menu, Cart, CartItem, Order, Customer, Category.\n"
            f"Требования:\n{document_content}"
        )

    def _normalize_structure_payload(
        self,
        parsed_payload: dict[str, Any] | None,
        document_content: str,
    ) -> dict[str, Any]:
        payload = parsed_payload or {}
        system_name = str(payload.get("system_name") or "Generated Project")
        domain_entities = self._as_text_list(payload.get("domain_entities")) or self._infer_entities(document_content)
        ui_screens = self._as_text_list(payload.get("ui_screens")) or ["Дашборд", "Список сущностей", "Карточка проекта"]
        backend_modules = self._as_text_list(payload.get("backend_modules")) or ["projects", "requirements", "generation", "deployment"]
        default_functionals = self._default_functional_requirements(document_content)
        default_user_stories = self._default_user_stories(document_content)
        default_acceptance = self._default_acceptance_criteria(document_content)
        return {
            "system_name": system_name,
            "functional_requirements": self._as_text_list(payload.get("functional_requirements")) or default_functionals,
            "non_functional_requirements": self._as_text_list(payload.get("non_functional_requirements")) or ["Локальный запуск в Docker", "Прозрачный UI"],
            "domain_entities": domain_entities,
            "user_stories": self._as_text_list(payload.get("user_stories")) or default_user_stories,
            "acceptance_criteria": self._as_text_list(payload.get("acceptance_criteria")) or default_acceptance,
            "constraints": self._as_text_list(payload.get("constraints")) or ["MVP ориентирован на локальный запуск"],
            "ui_screens": ui_screens,
            "backend_modules": backend_modules,
            "test_scenarios": self._as_text_list(payload.get("test_scenarios")) or ["Проверка healthcheck", "Создание записи", "Dry-run deploy"],
            "risks": self._as_text_list(payload.get("risks")) or ["Нужна ручная валидация generated UI"],
            "gaps_and_conflicts": self._as_text_list(payload.get("gaps_and_conflicts")) or ["Требования могут требовать дополнительной детализации"],
        }

    def _render_structure_markdown(self, payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# Структура требований: {payload['system_name']}",
                "## Функциональные требования",
                *[f"- {item}" for item in self._as_text_list(payload.get("functional_requirements"))],
                "## Нефункциональные требования",
                *[f"- {item}" for item in self._as_text_list(payload.get("non_functional_requirements"))],
                "## Доменные сущности",
                *[f"- {item}" for item in self._as_text_list(payload.get("domain_entities"))],
                "## UI-экраны",
                *[f"- {item}" for item in self._as_text_list(payload.get("ui_screens"))],
                "## Backend-модули",
                *[f"- {item}" for item in self._as_text_list(payload.get("backend_modules"))],
                "## Риски и пробелы",
                *[
                    f"- {item}"
                    for item in self._as_text_list(payload.get("risks")) + self._as_text_list(payload.get("gaps_and_conflicts"))
                ],
            ]
        )

    def _as_text_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _infer_entities(self, document_content: str) -> list[str]:
        mappings = [
            ("польз", "User"),
            ("рол", "Role"),
            ("проект", "Project"),
            ("задач", "Task"),
            ("коммент", "Comment"),
            ("уведом", "Notification"),
            ("sla", "SLAEvent"),
            ("пиц", "Pizza"),
            ("меню", "Menu"),
            ("корзин", "Cart"),
            ("заказ", "Order"),
            ("клиент", "Customer"),
            ("покупат", "Customer"),
            ("достав", "Delivery"),
            ("категор", "Category"),
        ]
        entities = [entity for token, entity in mappings if token in document_content.lower()]
        return entities or ["Project", "Task", "Comment"]

    def _draft_requirements_markdown(
        self,
        *,
        description: str,
        adapter: BaseLLMAdapter,
        model: str,
        generation_mode: str = "auto",
    ) -> str:
        mode = generation_mode.lower()
        if mode == "template":
            return self._draft_requirements_template(description)
        if adapter.provider_name != "fake" and adapter.is_available():
            try:
                result = adapter.generate_text(prompt=self._draft_prompt(description), model=model)
                content = result.content.strip()
                if content:
                    return content
            except Exception as exc:
                if mode == "llm":
                    raise ValueError(str(exc)) from exc
        entities = self._infer_entities(description)
        screens = self._infer_screens(description)
        return self._draft_requirements_template(description, entities=entities, screens=screens)

    def _draft_requirements_template(
        self,
        description: str,
        *,
        entities: list[str] | None = None,
        screens: list[str] | None = None,
    ) -> str:
        entities = entities or self._infer_entities(description)
        screens = screens or self._infer_screens(description)
        return dedent(
            f"""
            # Требования к системе

            ## Краткое описание
            {description.strip()}

            ## Функциональные требования
            {"".join(f"- {item}\n" for item in self._default_functional_requirements(description)).rstrip()}

            ## Нефункциональные требования
            - Локальный запуск через Docker Compose.
            - Понятный web-интерфейс для демонстрации.
            - Возможность последующей генерации тестов и деплоя.

            ## Доменные сущности
            {"".join(f"- {entity}\n" for entity in entities).rstrip()}

            ## Пользовательские сценарии
            {"".join(f"- {item}\n" for item in self._default_user_stories(description)).rstrip()}

            ## Критерии приемки
            {"".join(f"- {item}\n" for item in self._default_acceptance_criteria(description)).rstrip()}

            ## Предполагаемые UI-экраны
            {"".join(f"- {screen}\n" for screen in screens).rstrip()}
            """
        ).strip() + "\n"

    def _draft_prompt(self, description: str) -> str:
        return (
            "На основе краткого описания системы подготовь полноценный Markdown-документ требований на русском языке. "
            "Нужны разделы: краткое описание, функциональные требования, нефункциональные требования, "
            "доменные сущности, пользовательские сценарии, критерии приемки, предполагаемые UI-экраны. "
            "Требования должны быть предметными, а не абстрактными. "
            "Если речь идёт про заказ пиццы, обязательно опиши меню, карточки пицц, корзину, оформление заказа, фейковые данные и административный просмотр заказов. "
            "Верни только Markdown.\n"
            f"Описание системы:\n{description}"
        )

    def _infer_screens(self, description: str) -> list[str]:
        screens = ["Дашборд", "Список сущностей", "Форма создания/редактирования"]
        lowered = description.lower()
        if "пиц" in lowered or "меню" in lowered:
            screens = ["Главная", "Меню", "Карточка пиццы", "Корзина", "Оформление заказа", "История заказов"]
        if "аналит" in lowered:
            screens.append("Аналитика")
        if "уведом" in lowered:
            screens.append("Уведомления")
        if "истор" in lowered:
            screens.append("История изменений")
        return screens

    def _default_functional_requirements(self, description: str) -> list[str]:
        lowered = description.lower()
        if "пиц" in lowered or "меню" in lowered or "корзин" in lowered:
            return [
                "Пользователь должен видеть каталог пицц с ценами, размерами и описанием.",
                "Пользователь должен уметь добавлять позиции в корзину и менять количество товаров.",
                "Система должна поддерживать оформление заказа на основе фейковых данных без реальной оплаты.",
                "Должен быть экран просмотра заказов и статусов обработки.",
                "Система должна содержать демонстрационные позиции меню и готовые примеры заказов.",
            ]
        return [
            "Система должна поддерживать управление основными сущностями проекта.",
            "Пользователь должен видеть список записей, карточки и формы создания.",
            "Должны отображаться статусы, история изменений и ключевые сценарии работы.",
        ]

    def _default_user_stories(self, description: str) -> list[str]:
        lowered = description.lower()
        if "пиц" in lowered or "меню" in lowered or "корзин" in lowered:
            return [
                "Как посетитель, я хочу открыть меню пицц и быстро добавить товар в корзину.",
                "Как клиент, я хочу оформить заказ на фейковых данных и увидеть итоговую сумму.",
                "Как менеджер, я хочу просматривать список заказов и их статусы.",
            ]
        return [
            "Как пользователь, я хочу управлять данными проекта через веб-интерфейс.",
            "Как аналитик, я хочу видеть структуру требований и артефакты проекта.",
            "Как разработчик, я хочу развернуть generated приложение локально.",
        ]

    def _default_acceptance_criteria(self, description: str) -> list[str]:
        lowered = description.lower()
        if "пиц" in lowered or "меню" in lowered or "корзин" in lowered:
            return [
                "На главной странице отображается меню пицц с фейковыми позициями.",
                "Пользователь может добавить пиццу в корзину и увидеть итоговую сумму.",
                "Можно создать заказ без внешней платёжной интеграции.",
                "Приложение разворачивается локально и отвечает по healthcheck.",
            ]
        return [
            "Приложение запускается локально и показывает основные сущности.",
            "Можно открыть дашборд и перейти на страницы сущностей.",
            "Можно создать запись через форму.",
        ]
