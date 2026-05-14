from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentExecution, AgentHandoff, AgentMemorySnapshot, AgentProfile
from app.domain.enums.common import ApprovalMode, RunStatus
from app.providers.base import BaseLLMAdapter

DEFAULT_AGENT_PROFILES = [
    {
        "name": "RequirementsAnalystAgent",
        "role": "Аналитик требований",
        "system_prompt": "Анализирует текст требований и готовит структурированное описание.",
    },
    {
        "name": "SoftwareArchitectAgent",
        "role": "Архитектор",
        "system_prompt": "Предлагает архитектуру и следит за разделением ответственности.",
    },
    {
        "name": "CodeGeneratorAgent",
        "role": "Генератор кода",
        "system_prompt": "Генерирует backend/frontend каркас и артефакты.",
    },
    {
        "name": "TestEngineerAgent",
        "role": "Инженер по тестированию",
        "system_prompt": "Формирует тестовые сценарии и тестовые артефакты.",
    },
    {
        "name": "DeploymentAgent",
        "role": "Инженер деплоя",
        "system_prompt": "Готовит deployment bundle и проверяет готовность к контейнерному запуску.",
    },
    {
        "name": "ReviewerAgent",
        "role": "Ревьюер",
        "system_prompt": "Проверяет артефакты и риски пайплайна.",
    },
]


class AgentOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._bootstrap()

    def _bootstrap(self) -> None:
        for profile in DEFAULT_AGENT_PROFILES:
            existing = self.db.scalar(select(AgentProfile).where(AgentProfile.name == profile["name"]))
            if existing:
                continue
            self.db.add(
                AgentProfile(
                    name=profile["name"],
                    role=profile["role"],
                    system_prompt=profile["system_prompt"],
                    allowed_llm_providers=["fake", "openai", "anthropic", "openrouter"],
                    allowed_mcp_servers=["local-file-project", "project-knowledge"],
                    allowed_tools=["list_projects", "get_project_summary", "latest_requirement_structure"],
                    execution_policy={"mode": "serial"},
                    approval_mode=ApprovalMode.ALWAYS.value,
                    retry_policy={"max_attempts": 2},
                    timeout_seconds=120,
                    enabled=True,
                )
            )
        self.db.commit()

    def list_agents(self) -> list[AgentProfile]:
        return list(self.db.scalars(select(AgentProfile).order_by(AgentProfile.name)))

    def execute(
        self,
        *,
        project_id: str,
        agent_name: str,
        task: str,
        payload: dict[str, Any],
        approved: bool,
        adapter: BaseLLMAdapter,
    ) -> AgentExecution:
        profile = self.db.scalar(select(AgentProfile).where(AgentProfile.name == agent_name))
        if profile is None:
            raise ValueError("Профиль агента не найден")
        if profile.approval_mode == ApprovalMode.ALWAYS.value and not approved:
            raise ValueError("Для запуска агента требуется подтверждение пользователя")
        prompt = f"{profile.system_prompt}\nЗадача: {task}\nДанные: {payload}"
        llm_result = adapter.generate_text(prompt=prompt, model="demo-agent-v1")
        execution = AgentExecution(
            project_id=project_id,
            agent_profile_id=profile.id,
            input_payload={"task": task, "payload": payload},
            output_payload={"result": llm_result.content},
            status=RunStatus.COMPLETED.value,
            logs=f"Agent {agent_name} executed task: {task}",
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        self.db.add(
            AgentMemorySnapshot(
                project_id=project_id,
                agent_name=agent_name,
                snapshot_payload={"last_task": task, "last_result": llm_result.content},
            )
        )
        self.db.add(
            AgentHandoff(
                project_id=project_id,
                from_agent=agent_name,
                to_agent="ReviewerAgent" if agent_name != "ReviewerAgent" else agent_name,
                artifact_refs={"execution_id": execution.id},
                notes="Автоматически созданный handoff для demo pipeline",
            )
        )
        self.db.commit()
        return execution

