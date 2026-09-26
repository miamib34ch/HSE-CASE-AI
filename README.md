# HSE-CASE-AI

Рабочий MVP дипломного проекта: прототип CASE-системы для автоматизации разработки ПО с применением генеративного ИИ, MCP и агентной оркестрации.

## Что входит в MVP
- backend на FastAPI + SQLAlchemy + Celery;
- frontend на React + TypeScript + Vite + Tailwind;
- PostgreSQL, Redis, Nginx, Docker Compose;
- demo mode без реальных API-ключей;
- единый слой LLM adapters;
- CASE workflow: requirements -> structure -> confirm -> code -> tests -> deploy;
- генерация локально разворачиваемого scaffold web-приложения с preview URL;
- встроенный менеджер артефактов с загрузкой, удалением, редактором и preview изображений;
- визуализация Mermaid-схем прямо в UI;
- MCP client/server layer;
- агентный слой с журналированием выполнения;
- документация для запуска и защиты.

## Структура
- `apps/backend` — backend API, storage, workflow, MCP, agents.
- `apps/frontend` — веб-интерфейс.
- `packages/shared-schemas` — общие схемы и статусы.
- `docs` — архитектура, запуск, MCP, demo-script.
- `examples` — пример требований.
- `infra` — nginx и postgres init.
- `storage` — файловое хранилище проектов и артефактов.

## Быстрый запуск
```bash
cp .env.example .env
docker compose up --build
```

UI будет доступен на `http://localhost:8080`, backend API — на `http://localhost:8000`.

## Demo mode
- По умолчанию активен `FakeLLMAdapter`.
- Система не падает без API-ключей.
- Dry-run deployment подходит для показа на защите.
- Real deploy использует последний generated snapshot и поднимает локальный preview сайта на отдельном порту `localhost:91xx`.
- Python MCP SDK подключается опционально; без него HTTP MCP bridge продолжает работать.

## Локальная разработка
```bash
python3 -m pip install -e ".[dev]"
cd apps/frontend && npm install
docker compose -f docker-compose.dev.yml up --build
```

## Документация
- [Архитектура](docs/architecture.md)
- [План реализации](docs/implementation-plan.md)
- [Развёртывание](docs/deployment.md)
- [Провайдеры](docs/provider-integration.md)
- [MCP-архитектура](docs/mcp-architecture.md)
- [Сценарий защиты](docs/thesis-demo-script.md)
