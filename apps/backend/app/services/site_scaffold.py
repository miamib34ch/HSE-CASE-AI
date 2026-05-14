from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from hashlib import md5
from pathlib import Path
from textwrap import dedent
from typing import Any, cast


@dataclass(slots=True)
class SiteEntity:
    name: str
    label: str
    slug: str
    fields: list[dict[str, str]]
    records: list[dict[str, str]]


@dataclass(slots=True)
class SiteSpec:
    app_name: str
    description: str
    accent_color: str
    hero_title: str
    hero_subtitle: str
    pages: list[str]
    entities: list[SiteEntity]
    preview_port: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "description": self.description,
            "accent_color": self.accent_color,
            "hero_title": self.hero_title,
            "hero_subtitle": self.hero_subtitle,
            "pages": self.pages,
            "preview_port": self.preview_port,
            "entities": [
                {
                    "name": entity.name,
                    "label": entity.label,
                    "slug": entity.slug,
                    "fields": entity.fields,
                    "records": entity.records,
                }
                for entity in self.entities
            ],
        }


@dataclass(slots=True)
class GeneratedFileEntry:
    text: str | None = None
    binary: bytes | None = None
    media_type: str | None = None

    @property
    def is_binary(self) -> bool:
        return self.binary is not None

    @property
    def has_content(self) -> bool:
        return bool(self.binary) or bool(self.text)


def build_site_spec(
    *,
    project_id: str,
    project_name: str,
    project_description: str,
    requirement_structure: dict[str, Any],
    llm_payload: dict[str, Any] | None = None,
) -> SiteSpec:
    app_name = str(
        (llm_payload or {}).get("app_name")
        or requirement_structure.get("system_name")
        or project_name
        or "Generated Project"
    )
    description = project_description or str(
        (llm_payload or {}).get("description")
        or "Сгенерированное локально web-приложение на основе подтверждённых требований."
    )
    accent_color = str((llm_payload or {}).get("accent_color") or "#F97316")
    hero_title = str((llm_payload or {}).get("hero_title") or f"{app_name}: рабочий MVP")
    hero_subtitle = str(
        (llm_payload or {}).get("hero_subtitle")
        or "Локально разворачиваемое приложение с FastAPI API, динамическим UI и демонстрационными данными."
    )
    port = 9100 + (int(md5(project_id.encode("utf-8")).hexdigest()[:6], 16) % 300)

    llm_entities = _entities_from_llm_payload(llm_payload)
    entity_names = cast(list[Any], requirement_structure.get("domain_entities", []))
    entities = [_entity_for_name(str(name)) for name in entity_names]
    normalized_entities = llm_entities or [entity for entity in entities if entity is not None]
    if not normalized_entities:
        normalized_entities = [
            SiteEntity(
                name="Project",
                label="Проекты",
                slug="projects",
                fields=[
                    {"name": "title", "label": "Название", "type": "text"},
                    {"name": "status", "label": "Статус", "type": "text"},
                    {"name": "owner", "label": "Владелец", "type": "text"},
                ],
                records=[
                    {"id": "prj-1", "title": "Generated Project", "status": "in_progress", "owner": "Team A"},
                ],
            ),
            SiteEntity(
                name="Task",
                label="Задачи",
                slug="tasks",
                fields=[
                    {"name": "title", "label": "Название", "type": "text"},
                    {"name": "status", "label": "Статус", "type": "text"},
                    {"name": "assignee", "label": "Исполнитель", "type": "text"},
                ],
                records=[
                    {"id": "tsk-1", "title": "Первая задача", "status": "planned", "assignee": "Team A"},
                ],
            ),
            SiteEntity(
                name="Comment",
                label="Комментарии",
                slug="comments",
                fields=[
                    {"name": "author", "label": "Автор", "type": "text"},
                    {"name": "message", "label": "Сообщение", "type": "text"},
                ],
                records=[
                    {"id": "cmt-1", "author": "System", "message": "Generated scaffold initialised"},
                ],
            ),
        ]
    entities_final = normalized_entities
    llm_pages = _pages_from_llm_payload(llm_payload)
    pages = llm_pages or [
        "Дашборд",
        *[entity.label for entity in entities_final],
        "Сценарии",
        "Риски",
    ]

    return SiteSpec(
        app_name=app_name,
        description=description,
        accent_color=accent_color,
        hero_title=hero_title,
        hero_subtitle=hero_subtitle,
        pages=pages,
        entities=entities_final,
        preview_port=port,
    )


def extract_site_spec_json(raw_text: str) -> dict[str, Any] | None:
    candidates: list[str] = []
    if "```json" in raw_text:
        for part in raw_text.split("```json")[1:]:
            candidates.append(part.split("```", 1)[0].strip())
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(raw_text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return cast(dict[str, Any], value)
    return None


def extract_generated_files(raw_text: str) -> dict[str, str] | None:
    entries = extract_generated_file_entries(raw_text)
    if entries is None:
        return None
    files: dict[str, str] = {}
    for path, entry in entries.items():
        if entry.text is not None:
            files[path] = entry.text
    return files or None


def extract_generated_file_entries(raw_text: str) -> dict[str, GeneratedFileEntry] | None:
    payload = extract_site_spec_json(raw_text)
    if payload is None:
        return None
    raw_files = payload.get("files")
    if not isinstance(raw_files, dict):
        raw_files = payload.get("artifacts")
    if isinstance(raw_files, list):
        mapped_files = _files_from_list(raw_files)
        return mapped_files or None
    if not isinstance(raw_files, dict) and _looks_like_file_map(payload):
        raw_files = payload
    if not isinstance(raw_files, dict):
        return None
    files: dict[str, GeneratedFileEntry] = {}
    for path, content in raw_files.items():
        normalized_path = str(path).strip()
        if not normalized_path:
            continue
        files[normalized_path] = _normalize_file_entry(content, normalized_path)
    return files or None


def _looks_like_file_map(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    candidates = 0
    for key, value in payload.items():
        key_text = str(key)
        if "/" in key_text or "." in key_text:
            candidates += 1
            if not isinstance(value, (str, int, float, bool)):
                return False
    return candidates > 0


def _files_from_list(raw_files: list[Any]) -> dict[str, GeneratedFileEntry]:
    files: dict[str, GeneratedFileEntry] = {}
    for item in raw_files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("name") or item.get("file") or "").strip()
        if not path:
            continue
        content_value = item.get("content")
        if content_value in (None, "", []) and any(
            key in item for key in ("data", "base64", "bytes", "text", "body", "value")
        ):
            content_value = {
                key: item.get(key)
                for key in ("content", "data", "base64", "bytes", "text", "body", "value", "mime_type", "content_type")
                if key in item
            }
        files[path] = _normalize_file_entry(content_value, path)
    return files


def _normalize_file_content(content: Any) -> str:
    entry = _normalize_file_entry(content, "")
    if entry.text is not None:
        return entry.text
    if entry.binary is not None:
        return base64.b64encode(entry.binary).decode("ascii")
    return ""


def _normalize_file_entry(content: Any, path: str) -> GeneratedFileEntry:
    if isinstance(content, dict):
        media_type = _string_or_none(
            content.get("mime_type") or content.get("content_type") or content.get("media_type")
        )
        for key in ("content", "text", "body", "value", "data", "base64", "bytes"):
            if key not in content:
                continue
            entry = _normalize_file_entry(content[key], path)
            if entry.has_content:
                if entry.media_type is None:
                    entry.media_type = media_type
                return entry
        return GeneratedFileEntry(
            text=json.dumps(content, ensure_ascii=False, indent=2),
            media_type=media_type,
        )
    if isinstance(content, list):
        return GeneratedFileEntry(text="\n".join(str(item) for item in content))
    if isinstance(content, (bytes, bytearray)):
        return GeneratedFileEntry(binary=bytes(content), media_type=_guess_media_type(path))
    text_content = str(content or "")
    if not text_content:
        return GeneratedFileEntry(text="")
    data_uri = _decode_data_uri(text_content)
    if data_uri is not None:
        binary, media_type = data_uri
        return GeneratedFileEntry(binary=binary, media_type=media_type or _guess_media_type(path))
    if _looks_like_base64_payload(text_content, path):
        try:
            return GeneratedFileEntry(
                binary=base64.b64decode(text_content, validate=True),
                media_type=_guess_media_type(path),
            )
        except (ValueError, binascii.Error):
            pass
    return GeneratedFileEntry(text=text_content)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _decode_data_uri(value: str) -> tuple[bytes, str | None] | None:
    if not value.startswith("data:") or ";base64," not in value:
        return None
    header, encoded = value.split(",", 1)
    media_type = header[5:].split(";", 1)[0].strip() or None
    try:
        return base64.b64decode(encoded, validate=True), media_type
    except (ValueError, binascii.Error):
        return None


def _looks_like_base64_payload(value: str, path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp"}:
        return False
    compact = "".join(value.split())
    return len(compact) > 64 and len(compact) % 4 == 0


def _guess_media_type(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".bmp": "image/bmp",
    }
    return mapping.get(suffix)


def build_site_files(spec: SiteSpec) -> dict[str, str]:
    spec_json = json.dumps(spec.to_dict(), ensure_ascii=False, indent=2)
    runtime_json = json.dumps(
        {entity.slug: entity.records for entity in spec.entities},
        ensure_ascii=False,
        indent=2,
    )

    files = {
        "README.md": _root_readme(spec),
        "generated/ARCHITECTURE.md": _architecture(spec),
        "generated/API_NOTES.md": _api_notes(spec),
        "docker-compose.generated.yml": _docker_compose(spec),
        "backend/Dockerfile": _backend_dockerfile(),
        "backend/requirements.txt": _backend_requirements(),
        "backend/app/main.py": _backend_main(),
        "backend/app/app_spec.json": spec_json,
        "backend/app/data/runtime.json": runtime_json,
        "backend/app/static/index.html": _frontend_index(spec),
        "backend/app/static/app.js": _frontend_app_js(spec),
        "backend/app/static/styles.css": _frontend_styles(spec),
    }
    return files


def _entity_for_name(name: str) -> SiteEntity | None:
    normalized = name.strip()
    if not normalized:
        return None
    lower = normalized.lower()
    mapping: dict[str, SiteEntity] = {
        "user": SiteEntity(
            name="User",
            label="Пользователи",
            slug="users",
            fields=[
                {"name": "full_name", "label": "Имя", "type": "text"},
                {"name": "email", "label": "Email", "type": "email"},
                {"name": "role", "label": "Роль", "type": "text"},
            ],
            records=[
                {"id": "usr-1", "full_name": "Анна Смирнова", "email": "anna@example.local", "role": "Manager"},
                {"id": "usr-2", "full_name": "Илья Петров", "email": "ilya@example.local", "role": "Developer"},
            ],
        ),
        "role": SiteEntity(
            name="Role",
            label="Роли",
            slug="roles",
            fields=[
                {"name": "name", "label": "Название", "type": "text"},
                {"name": "permissions", "label": "Права", "type": "text"},
            ],
            records=[
                {"id": "role-1", "name": "Manager", "permissions": "projects,tasks,analytics"},
                {"id": "role-2", "name": "Developer", "permissions": "tasks,comments"},
            ],
        ),
        "project": SiteEntity(
            name="Project",
            label="Проекты",
            slug="projects",
            fields=[
                {"name": "title", "label": "Название", "type": "text"},
                {"name": "status", "label": "Статус", "type": "text"},
                {"name": "owner", "label": "Владелец", "type": "text"},
                {"name": "deadline", "label": "Дедлайн", "type": "date"},
            ],
            records=[
                {"id": "prj-1", "title": "TaskFlow Platform", "status": "in_progress", "owner": "Анна", "deadline": "2026-04-01"},
                {"id": "prj-2", "title": "Client Portal", "status": "planning", "owner": "Илья", "deadline": "2026-05-15"},
            ],
        ),
        "task": SiteEntity(
            name="Task",
            label="Задачи",
            slug="tasks",
            fields=[
                {"name": "title", "label": "Название", "type": "text"},
                {"name": "status", "label": "Статус", "type": "text"},
                {"name": "priority", "label": "Приоритет", "type": "text"},
                {"name": "assignee", "label": "Исполнитель", "type": "text"},
            ],
            records=[
                {"id": "tsk-1", "title": "Сделать UI артефактов", "status": "done", "priority": "high", "assignee": "Анна"},
                {"id": "tsk-2", "title": "Подключить local deploy", "status": "in_progress", "priority": "medium", "assignee": "Илья"},
            ],
        ),
        "comment": SiteEntity(
            name="Comment",
            label="Комментарии",
            slug="comments",
            fields=[
                {"name": "author", "label": "Автор", "type": "text"},
                {"name": "message", "label": "Сообщение", "type": "text"},
                {"name": "created_at", "label": "Создан", "type": "datetime-local"},
            ],
            records=[
                {"id": "cmt-1", "author": "Анна", "message": "Сначала финализируем требования.", "created_at": "2026-03-20T10:00"},
                {"id": "cmt-2", "author": "Илья", "message": "Deploy готов для dry-run.", "created_at": "2026-03-20T13:30"},
            ],
        ),
        "notification": SiteEntity(
            name="Notification",
            label="Уведомления",
            slug="notifications",
            fields=[
                {"name": "title", "label": "Заголовок", "type": "text"},
                {"name": "channel", "label": "Канал", "type": "text"},
                {"name": "state", "label": "Состояние", "type": "text"},
            ],
            records=[
                {"id": "ntf-1", "title": "Просрочен SLA по задаче TSK-2", "channel": "email", "state": "new"},
                {"id": "ntf-2", "title": "Новый комментарий в проекте", "channel": "ui", "state": "read"},
            ],
        ),
        "slaevent": SiteEntity(
            name="SLAEvent",
            label="SLA события",
            slug="sla-events",
            fields=[
                {"name": "rule_name", "label": "Правило", "type": "text"},
                {"name": "state", "label": "Состояние", "type": "text"},
                {"name": "due_at", "label": "Срок", "type": "datetime-local"},
            ],
            records=[
                {"id": "sla-1", "rule_name": "Ответ на комментарий", "state": "ok", "due_at": "2026-03-21T12:00"},
                {"id": "sla-2", "rule_name": "Обновление статуса", "state": "risk", "due_at": "2026-03-20T18:00"},
            ],
        ),
        "pizza": SiteEntity(
            name="Pizza",
            label="Пиццы",
            slug="pizzas",
            fields=[
                {"name": "name", "label": "Название", "type": "text"},
                {"name": "price", "label": "Цена", "type": "number"},
                {"name": "size", "label": "Размер", "type": "text"},
                {"name": "category", "label": "Категория", "type": "text"},
            ],
            records=[
                {"id": "pz-1", "name": "Маргарита", "price": "499", "size": "30 см", "category": "Классика"},
                {"id": "pz-2", "name": "Пепперони", "price": "649", "size": "35 см", "category": "Хиты"},
            ],
        ),
        "menu": SiteEntity(
            name="Menu",
            label="Меню",
            slug="menu",
            fields=[
                {"name": "section", "label": "Раздел", "type": "text"},
                {"name": "highlight", "label": "Описание", "type": "text"},
            ],
            records=[
                {"id": "menu-1", "section": "Пиццы", "highlight": "Классические и фирменные позиции"},
                {"id": "menu-2", "section": "Комбо", "highlight": "Готовые наборы с напитками"},
            ],
        ),
        "cart": SiteEntity(
            name="Cart",
            label="Корзина",
            slug="carts",
            fields=[
                {"name": "customer_name", "label": "Клиент", "type": "text"},
                {"name": "items_count", "label": "Количество позиций", "type": "number"},
                {"name": "total_price", "label": "Сумма", "type": "number"},
            ],
            records=[
                {"id": "cart-1", "customer_name": "Гость", "items_count": "2", "total_price": "1148"},
            ],
        ),
        "cartitem": SiteEntity(
            name="CartItem",
            label="Позиции корзины",
            slug="cart-items",
            fields=[
                {"name": "pizza_name", "label": "Товар", "type": "text"},
                {"name": "quantity", "label": "Количество", "type": "number"},
                {"name": "price", "label": "Цена", "type": "number"},
            ],
            records=[
                {"id": "cart-item-1", "pizza_name": "Маргарита", "quantity": "1", "price": "499"},
                {"id": "cart-item-2", "pizza_name": "Пепперони", "quantity": "1", "price": "649"},
            ],
        ),
        "order": SiteEntity(
            name="Order",
            label="Заказы",
            slug="orders",
            fields=[
                {"name": "customer_name", "label": "Клиент", "type": "text"},
                {"name": "status", "label": "Статус", "type": "text"},
                {"name": "address", "label": "Адрес", "type": "text"},
                {"name": "total_price", "label": "Сумма", "type": "number"},
            ],
            records=[
                {"id": "ord-1", "customer_name": "Алексей", "status": "preparing", "address": "ул. Ленина, 10", "total_price": "1148"},
                {"id": "ord-2", "customer_name": "Мария", "status": "delivered", "address": "ул. Гагарина, 4", "total_price": "899"},
            ],
        ),
        "customer": SiteEntity(
            name="Customer",
            label="Клиенты",
            slug="customers",
            fields=[
                {"name": "full_name", "label": "Имя", "type": "text"},
                {"name": "phone", "label": "Телефон", "type": "text"},
                {"name": "address", "label": "Адрес", "type": "text"},
            ],
            records=[
                {"id": "cus-1", "full_name": "Алексей Иванов", "phone": "+7 900 111-22-33", "address": "ул. Ленина, 10"},
                {"id": "cus-2", "full_name": "Мария Соколова", "phone": "+7 900 999-88-77", "address": "ул. Гагарина, 4"},
            ],
        ),
        "category": SiteEntity(
            name="Category",
            label="Категории",
            slug="categories",
            fields=[
                {"name": "name", "label": "Название", "type": "text"},
                {"name": "description", "label": "Описание", "type": "text"},
            ],
            records=[
                {"id": "cat-1", "name": "Классика", "description": "Популярные вкусы"},
                {"id": "cat-2", "name": "Острая", "description": "Для любителей перца"},
            ],
        ),
    }
    if lower in mapping:
        return mapping[lower]
    slug = normalized.lower().replace(" ", "-").replace("_", "-")
    label = normalized if normalized.endswith("ы") else f"{normalized}ы"
    return SiteEntity(
        name=normalized,
        label=label,
        slug=slug,
        fields=[
            {"name": "name", "label": "Название", "type": "text"},
            {"name": "status", "label": "Статус", "type": "text"},
            {"name": "owner", "label": "Ответственный", "type": "text"},
        ],
        records=[
            {"id": f"{slug}-1", "name": f"{normalized} 1", "status": "active", "owner": "Team A"},
            {"id": f"{slug}-2", "name": f"{normalized} 2", "status": "planned", "owner": "Team B"},
        ],
    )


def _root_readme(spec: SiteSpec) -> str:
    return dedent(
        f"""
        # {spec.app_name}

        Сгенерированное приложение для локального запуска.

        ## Запуск

        ```bash
        docker compose -f docker-compose.generated.yml up --build
        ```

        После запуска интерфейс будет доступен на `http://localhost:{spec.preview_port}`.
        """
    ).strip() + "\n"


def _entities_from_llm_payload(llm_payload: dict[str, Any] | None) -> list[SiteEntity]:
    if not llm_payload:
        return []
    raw_entities = llm_payload.get("entities")
    if not isinstance(raw_entities, list):
        return []
    entities: list[SiteEntity] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        label = str(item.get("label", "")).strip() or name
        slug = str(item.get("slug", "")).strip().lower().replace(" ", "-") or name.lower().replace(" ", "-")
        raw_fields = item.get("fields")
        fields: list[dict[str, str]] = []
        if isinstance(raw_fields, list):
            for field in raw_fields:
                if not isinstance(field, dict):
                    continue
                field_name = str(field.get("name", "")).strip()
                if not field_name:
                    continue
                fields.append(
                    {
                        "name": field_name,
                        "label": str(field.get("label", field_name)).strip() or field_name,
                        "type": str(field.get("type", "text")).strip() or "text",
                    }
                )
        raw_records = item.get("records")
        records: list[dict[str, str]] = []
        if isinstance(raw_records, list):
            for index, record in enumerate(raw_records, start=1):
                if not isinstance(record, dict):
                    continue
                normalized_record = {str(key): str(value) for key, value in record.items()}
                normalized_record.setdefault("id", f"{slug}-{index}")
                records.append(normalized_record)
        if name and fields:
            entities.append(
                SiteEntity(
                    name=name,
                    label=label,
                    slug=slug,
                    fields=fields,
                    records=records,
                )
            )
    return entities


def _pages_from_llm_payload(llm_payload: dict[str, Any] | None) -> list[str]:
    if not llm_payload:
        return []
    raw_pages = llm_payload.get("pages")
    if not isinstance(raw_pages, list):
        return []
    return [str(item).strip() for item in raw_pages if str(item).strip()]


def _architecture(spec: SiteSpec) -> str:
    entity_list = "\n".join(f"- {entity.label}" for entity in spec.entities)
    return dedent(
        f"""
        # Архитектура {spec.app_name}

        Приложение разворачивается как один контейнер FastAPI, который отдаёт:
        - REST API для сущностей;
        - статику frontend;
        - healthcheck и спецификацию проекта.

        ## Сущности
        {entity_list}

        ## Preview URL
        - http://localhost:{spec.preview_port}
        """
    ).strip() + "\n"


def _api_notes(spec: SiteSpec) -> str:
    entity_routes = "\n".join(f"- `/api/entities/{entity.slug}`" for entity in spec.entities)
    return dedent(
        f"""
        # API Notes

        ## Основные endpoints
        - `/api/health`
        - `/api/spec`
        {entity_routes}
        """
    ).strip() + "\n"


def _docker_compose(spec: SiteSpec) -> str:
    return dedent(
        f"""
        services:
          generated-app:
            build:
              context: .
              dockerfile: ./backend/Dockerfile
            ports:
              - "{spec.preview_port}:8000"
            restart: unless-stopped
        """
    ).strip() + "\n"


def _backend_dockerfile() -> str:
    return dedent(
        """
        FROM python:3.12-slim

        WORKDIR /app

        COPY backend/requirements.txt ./requirements.txt
        RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

        COPY backend/app ./app

        EXPOSE 8000

        CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
        """
    ).strip() + "\n"


def _backend_requirements() -> str:
    return "fastapi==0.135.1\nuvicorn[standard]==0.42.0\npydantic==2.12.5\n"


def _backend_main() -> str:
    return dedent(
        """
        from __future__ import annotations

        import json
        from pathlib import Path
        from uuid import uuid4

        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        APP_ROOT = Path(__file__).resolve().parent
        STATIC_ROOT = APP_ROOT / "static"
        DATA_ROOT = APP_ROOT / "data"
        SPEC_PATH = APP_ROOT / "app_spec.json"
        RUNTIME_PATH = DATA_ROOT / "runtime.json"

        app = FastAPI(title="Generated Local App")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")


        def load_spec() -> dict[str, object]:
            return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


        def load_runtime() -> dict[str, list[dict[str, object]]]:
            DATA_ROOT.mkdir(parents=True, exist_ok=True)
            if not RUNTIME_PATH.exists():
                RUNTIME_PATH.write_text("{}", encoding="utf-8")
            return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))


        def save_runtime(payload: dict[str, list[dict[str, object]]]) -> None:
            DATA_ROOT.mkdir(parents=True, exist_ok=True)
            RUNTIME_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


        @app.get("/api/health")
        def health() -> dict[str, object]:
            spec = load_spec()
            return {"ok": True, "app_name": spec.get("app_name"), "entities": len(spec.get("entities", []))}


        @app.get("/api/spec")
        def spec() -> dict[str, object]:
            payload = load_spec()
            runtime = load_runtime()
            payload["counts"] = {key: len(value) for key, value in runtime.items()}
            return payload


        @app.get("/api/entities/{entity_slug}")
        def list_entity_records(entity_slug: str) -> list[dict[str, object]]:
            runtime = load_runtime()
            if entity_slug not in runtime:
                raise HTTPException(status_code=404, detail="Сущность не найдена")
            return runtime[entity_slug]


        @app.post("/api/entities/{entity_slug}")
        def create_entity_record(entity_slug: str, payload: dict[str, object]) -> dict[str, object]:
            runtime = load_runtime()
            if entity_slug not in runtime:
                raise HTTPException(status_code=404, detail="Сущность не найдена")
            record = {"id": str(uuid4()), **payload}
            runtime[entity_slug].insert(0, record)
            save_runtime(runtime)
            return record


        @app.put("/api/entities/{entity_slug}/{record_id}")
        def update_entity_record(entity_slug: str, record_id: str, payload: dict[str, object]) -> dict[str, object]:
            runtime = load_runtime()
            if entity_slug not in runtime:
                raise HTTPException(status_code=404, detail="Сущность не найдена")
            for index, item in enumerate(runtime[entity_slug]):
                if str(item.get("id")) == record_id:
                    updated = {**item, **payload, "id": record_id}
                    runtime[entity_slug][index] = updated
                    save_runtime(runtime)
                    return updated
            raise HTTPException(status_code=404, detail="Запись не найдена")


        @app.delete("/api/entities/{entity_slug}/{record_id}")
        def delete_entity_record(entity_slug: str, record_id: str) -> dict[str, str]:
            runtime = load_runtime()
            if entity_slug not in runtime:
                raise HTTPException(status_code=404, detail="Сущность не найдена")
            runtime[entity_slug] = [item for item in runtime[entity_slug] if str(item.get("id")) != record_id]
            save_runtime(runtime)
            return {"status": "deleted"}


        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC_ROOT / "index.html")
        """
    ).strip() + "\n"


def _frontend_index(spec: SiteSpec) -> str:
    return dedent(
        f"""
        <!DOCTYPE html>
        <html lang="ru">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>{spec.app_name}</title>
            <link rel="stylesheet" href="/static/styles.css" />
          </head>
          <body>
            <div id="app"></div>
            <script type="module" src="/static/app.js"></script>
          </body>
        </html>
        """
    ).strip() + "\n"


def _frontend_app_js(spec: SiteSpec) -> str:
    return dedent(
        f"""
        const app = document.getElementById("app");
        let appSpec = null;
        let activeEntity = null;

        async function request(path, options = {{}}) {{
          const response = await fetch(path, {{
            headers: {{"Content-Type": "application/json"}},
            ...options,
          }});
          if (!response.ok) {{
            const payload = await response.json().catch(() => ({{ detail: "Ошибка запроса" }}));
            throw new Error(payload.detail || "Ошибка запроса");
          }}
          return response.json();
        }}

        async function loadSpec() {{
          appSpec = await request("/api/spec");
          activeEntity = appSpec.entities[0]?.slug ?? null;
          render();
        }}

        function navMarkup() {{
          return appSpec.entities.map((entity) => `
            <button class="nav-pill ${{activeEntity === entity.slug ? "active" : ""}}" data-entity="${{entity.slug}}">
              ${{entity.label}}
            </button>
          `).join("");
        }}

        function dashboardMarkup() {{
          return `
            <section class="hero">
              <div>
                <div class="eyebrow">Generated locally</div>
                <h1>{spec.hero_title}</h1>
                <p>{spec.hero_subtitle}</p>
              </div>
              <div class="hero-meta">
                <div><span>Сущностей</span><strong>${{appSpec.entities.length}}</strong></div>
                <div><span>Экранов</span><strong>${{appSpec.pages.length}}</strong></div>
                <div><span>Preview</span><strong>:{spec.preview_port}</strong></div>
              </div>
            </section>
            <section class="cards">
              ${{appSpec.entities.map((entity) => `
                <article class="card">
                  <span>${{entity.label}}</span>
                  <strong>${{appSpec.counts?.[entity.slug] ?? 0}}</strong>
                  <p>Данные и формы создаются динамически на основе спецификации.</p>
                </article>
              `).join("")}}
            </section>
          `;
        }}

        function entityMarkup(entity, records) {{
          const headers = entity.fields.map((field) => `<th>${{field.label}}</th>`).join("");
          const rows = records.map((record) => `
            <tr>
              ${{entity.fields.map((field) => `<td>${{record[field.name] ?? ""}}</td>`).join("")}}
              <td><button class="delete-link" data-delete-id="${{record.id}}" data-delete-entity="${{entity.slug}}">Удалить</button></td>
            </tr>
          `).join("");
          const formFields = entity.fields.map((field) => `
            <label>
              <span>${{field.label}}</span>
              <input name="${{field.name}}" type="${{field.type}}" />
            </label>
          `).join("");
          return `
            <section class="entity-shell">
              <div class="section-header">
                <div>
                  <h2>${{entity.label}}</h2>
                  <p>CRUD-экран сгенерирован по структуре требований.</p>
                </div>
              </div>
              <div class="entity-grid">
                <div class="table-card">
                  <table>
                    <thead><tr>${{headers}}<th></th></tr></thead>
                    <tbody>${{rows || `<tr><td colspan="${{entity.fields.length + 1}}">Нет данных</td></tr>`}}</tbody>
                  </table>
                </div>
                <form class="form-card" data-entity-form="${{entity.slug}}">
                  <h3>Новая запись</h3>
                  ${{formFields}}
                  <button type="submit">Добавить</button>
                </form>
              </div>
            </section>
          `;
        }}

        async function renderEntitySection() {{
          const entity = appSpec.entities.find((item) => item.slug === activeEntity);
          if (!entity) {{
            return '<div class="empty">Сущность не найдена.</div>';
          }}
          const records = await request(`/api/entities/${{entity.slug}}`);
          return entityMarkup(entity, records);
        }}

        async function render() {{
          if (!appSpec) {{
            app.innerHTML = '<div class="loading">Загрузка...</div>';
            return;
          }}
          const entitySection = await renderEntitySection();
          app.innerHTML = `
            <div class="shell">
              <aside class="sidebar">
                <div class="brand">
                  <div class="brand-mark"></div>
                  <div>
                    <strong>{spec.app_name}</strong>
                    <span>{spec.description}</span>
                  </div>
                </div>
                <div class="nav-group">
                  ${{navMarkup()}}
                </div>
                <div class="meta-box">
                  <span>Сгенерировано CASE AI</span>
                  <strong>FastAPI + Dynamic UI</strong>
                </div>
              </aside>
              <main class="content">
                ${{dashboardMarkup()}}
                ${{entitySection}}
              </main>
            </div>
          `;
          bindEvents();
        }}

        function bindEvents() {{
          document.querySelectorAll("[data-entity]").forEach((button) => {{
            button.addEventListener("click", async () => {{
              activeEntity = button.dataset.entity;
              await render();
            }});
          }});
          document.querySelectorAll("[data-entity-form]").forEach((form) => {{
            form.addEventListener("submit", async (event) => {{
              event.preventDefault();
              const entitySlug = form.dataset.entityForm;
              const formData = new FormData(form);
              const payload = Object.fromEntries(formData.entries());
              await request(`/api/entities/${{entitySlug}}`, {{
                method: "POST",
                body: JSON.stringify(payload),
              }});
              await loadSpec();
            }});
          }});
          document.querySelectorAll("[data-delete-id]").forEach((button) => {{
            button.addEventListener("click", async () => {{
              await request(`/api/entities/${{button.dataset.deleteEntity}}/${{button.dataset.deleteId}}`, {{
                method: "DELETE",
              }});
              await loadSpec();
            }});
          }});
        }}

        loadSpec().catch((error) => {{
          app.innerHTML = `<div class="loading">Ошибка инициализации: ${{error.message}}</div>`;
        }});
        """
    ).strip() + "\n"


def _frontend_styles(spec: SiteSpec) -> str:
    return dedent(
        f"""
        :root {{
          --bg: #0b1120;
          --panel: #101a2f;
          --panel-alt: #16223d;
          --text: #edf2ff;
          --muted: #9fb0d1;
          --line: rgba(255, 255, 255, 0.08);
          --accent: {spec.accent_color};
        }}

        * {{
          box-sizing: border-box;
        }}

        body {{
          margin: 0;
          min-height: 100vh;
          font-family: "Inter", "Segoe UI", sans-serif;
          background:
            radial-gradient(circle at top left, rgba(249, 115, 22, 0.22), transparent 28%),
            linear-gradient(180deg, #09101f 0%, #0f172a 100%);
          color: var(--text);
        }}

        .shell {{
          display: grid;
          grid-template-columns: 280px 1fr;
          min-height: 100vh;
        }}

        .sidebar {{
          border-right: 1px solid var(--line);
          background: rgba(7, 13, 25, 0.9);
          padding: 24px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }}

        .brand {{
          display: flex;
          gap: 14px;
          align-items: center;
        }}

        .brand-mark {{
          width: 18px;
          height: 18px;
          border-radius: 6px;
          background: linear-gradient(135deg, var(--accent), #fb7185);
          box-shadow: 0 0 28px rgba(249, 115, 22, 0.45);
        }}

        .brand span, .meta-box span, .hero p, .card p, .section-header p {{
          color: var(--muted);
        }}

        .nav-group {{
          display: flex;
          flex-direction: column;
          gap: 10px;
        }}

        .nav-pill {{
          width: 100%;
          border: 1px solid var(--line);
          background: transparent;
          color: var(--text);
          text-align: left;
          border-radius: 18px;
          padding: 12px 14px;
          cursor: pointer;
        }}

        .nav-pill.active {{
          background: rgba(249, 115, 22, 0.12);
          border-color: rgba(249, 115, 22, 0.45);
        }}

        .meta-box {{
          margin-top: auto;
          padding: 16px;
          border-radius: 24px;
          border: 1px solid var(--line);
          background: rgba(255, 255, 255, 0.03);
        }}

        .content {{
          padding: 32px;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }}

        .hero {{
          display: flex;
          justify-content: space-between;
          gap: 20px;
          padding: 28px;
          border-radius: 32px;
          background: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
          border: 1px solid var(--line);
        }}

        .hero h1 {{
          margin: 10px 0 12px;
          font-size: 42px;
          line-height: 1.05;
        }}

        .eyebrow {{
          display: inline-flex;
          padding: 6px 12px;
          border-radius: 999px;
          border: 1px solid rgba(249, 115, 22, 0.4);
          color: #fdba74;
          text-transform: uppercase;
          font-size: 11px;
          letter-spacing: 0.2em;
        }}

        .hero-meta {{
          min-width: 220px;
          display: grid;
          gap: 12px;
        }}

        .hero-meta div, .card, .table-card, .form-card {{
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid var(--line);
          border-radius: 24px;
          padding: 18px;
        }}

        .hero-meta strong, .card strong {{
          display: block;
          margin-top: 10px;
          font-size: 28px;
        }}

        .cards {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
        }}

        .entity-grid {{
          display: grid;
          grid-template-columns: 1.5fr 0.8fr;
          gap: 18px;
        }}

        table {{
          width: 100%;
          border-collapse: collapse;
        }}

        th, td {{
          padding: 12px;
          border-bottom: 1px solid var(--line);
          text-align: left;
          font-size: 14px;
        }}

        th {{
          color: var(--muted);
          font-weight: 500;
        }}

        form {{
          display: grid;
          gap: 12px;
        }}

        label {{
          display: grid;
          gap: 6px;
          font-size: 14px;
          color: var(--muted);
        }}

        input, button {{
          border-radius: 16px;
          border: 1px solid var(--line);
          padding: 12px 14px;
          font: inherit;
        }}

        input {{
          background: rgba(255, 255, 255, 0.04);
          color: var(--text);
        }}

        button {{
          background: var(--accent);
          color: white;
          cursor: pointer;
        }}

        .delete-link {{
          background: transparent;
          color: #fda4af;
          border: 0;
          padding: 0;
        }}

        .loading, .empty {{
          padding: 24px;
        }}

        @media (max-width: 960px) {{
          .shell {{
            grid-template-columns: 1fr;
          }}

          .sidebar {{
            border-right: 0;
            border-bottom: 1px solid var(--line);
          }}

          .hero, .entity-grid {{
            grid-template-columns: 1fr;
            display: grid;
          }}

          .content {{
            padding: 20px;
          }}
        }}
        """
    ).strip() + "\n"
