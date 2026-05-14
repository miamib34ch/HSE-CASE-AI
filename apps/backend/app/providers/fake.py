from __future__ import annotations

from hashlib import md5
from typing import Any

from app.providers.base import LLMResult


class FakeLLMAdapter:
    provider_name = "fake"

    def is_available(self) -> bool:
        return True

    def _seed(self, value: str) -> int:
        return int(md5(value.encode("utf-8")).hexdigest()[:6], 16)

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        seed = self._seed(prompt)
        return LLMResult(
            provider=self.provider_name,
            model=model,
            content=f"Demo response #{seed} for model {model}",
            structured_output={"summary": "deterministic"},
            tokens_in=len(prompt.split()),
            tokens_out=24,
        )

    def generate_structured(
        self, *, prompt: str, model: str, schema_name: str
    ) -> LLMResult:
        system_name = "TaskFlow Demo"
        structured = {
            "functional_requirements": [
                "Управление проектами и задачами",
                "Комментарии и история изменений",
                "Фильтрация и SLA-мониторинг",
            ],
            "non_functional_requirements": [
                "Локальный контейнерный деплой",
                "Понятный веб-интерфейс",
                "Аудит критичных действий",
            ],
            "domain_entities": [
                "User",
                "Role",
                "Project",
                "Task",
                "Comment",
                "Notification",
                "SLAEvent",
            ],
            "user_stories": [
                "Как менеджер проекта, я хочу видеть backlog и загрузку команды.",
                "Как разработчик, я хочу обновлять статус задач и комментировать изменения.",
            ],
            "acceptance_criteria": [
                "Можно создать проект и задачу.",
                "История изменений фиксируется автоматически.",
                "Просрочки SLA видны в аналитике.",
            ],
            "constraints": ["MVP ориентирован на локальный запуск", "Demo mode должен работать без API-ключей"],
            "ui_screens": [
                "Дашборд",
                "Список проектов",
                "Карточка проекта",
                "Список задач",
                "История запусков",
            ],
            "backend_modules": [
                "projects",
                "requirements",
                "generation",
                "testing",
                "deployment",
                "mcp",
                "agents",
            ],
            "test_scenarios": [
                "Создание проекта",
                "Подтверждение структуры требований",
                "Dry-run deployment",
            ],
            "risks": [
                "Без реальных интеграций ответы demo-mode не отражают качество LLM",
                "Реальный deploy зависит от локального Docker",
            ],
            "gaps_and_conflicts": [
                "Не описана полноценная авторизация",
                "Не уточнены каналы внешних уведомлений",
            ],
            "system_name": system_name,
            "schema_name": schema_name,
        }
        risks = list(structured["risks"])
        gaps = list(structured["gaps_and_conflicts"])
        markdown = "\n".join(
            [
                f"# Структура требований: {system_name}",
                "## Функциональные требования",
                *[f"- {item}" for item in structured["functional_requirements"]],
                "## Нефункциональные требования",
                *[f"- {item}" for item in structured["non_functional_requirements"]],
                "## Доменные сущности",
                *[f"- {item}" for item in structured["domain_entities"]],
                "## Риски и пробелы",
                *[f"- {item}" for item in risks + gaps],
            ]
        )
        return LLMResult(
            provider=self.provider_name,
            model=model,
            content=markdown,
            structured_output=structured,
            tokens_in=len(prompt.split()),
            tokens_out=200,
        )

    def generate_code(self, *, prompt: str, model: str) -> LLMResult:
        structured = {
            "files": {
                "backend/app/main.py": "from fastapi import FastAPI\n\napp = FastAPI(title='Generated Demo App')\n",
                "frontend/src/App.tsx": "export function App(){return <div>Generated Demo App</div>}\n",
                "docker-compose.generated.yml": "services:\n  demo:\n    image: nginx:alpine\n",
                "generated/ARCHITECTURE.md": "# Generated Architecture\n\nDemo web application.\n",
                "generated/API_NOTES.md": "# API Notes\n\nCRUD endpoints for entities.\n",
                "generated/README.md": "# Generated Application\n\nRun with docker compose.\n",
            }
        }
        return LLMResult(
            provider=self.provider_name,
            model=model,
            content="Code generation completed",
            structured_output=structured,
            tokens_in=len(prompt.split()),
            tokens_out=350,
        )

    def generate_tests(self, *, prompt: str, model: str) -> LLMResult:
        structured = {
            "files": {
                "tests/test_services.py": "def test_demo_service():\n    assert True\n",
                "tests/test_api.py": "def test_healthcheck():\n    assert True\n",
                "tests/smoke.frontend.spec.ts": "test('smoke', async () => { expect(true).toBeTruthy(); });\n",
                "generated/TEST_PLAN.md": "# План тестирования\n\n- Smoke\n- API\n- Unit\n",
                "generated/TRACEABILITY.md": "# Traceability Matrix\n\n| Requirement | Artifact | Test |\n|---|---|---|\n| Создать проект | project_service | test_create_project |\n",
                "generated/junit.xml": "<testsuite tests='3' failures='0'></testsuite>",
            }
        }
        return LLMResult(
            provider=self.provider_name,
            model=model,
            content="Test generation completed",
            structured_output=structured,
            tokens_in=len(prompt.split()),
            tokens_out=180,
        )

    def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "provider": self.provider_name, "mode": "demo"}

    def list_models(self) -> list[str]:
        return ["demo-analysis-v1", "demo-code-v1", "demo-test-v1"]
