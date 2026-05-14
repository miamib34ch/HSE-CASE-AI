from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.projects import ProjectService
from app.services.requirements import RequirementService


class LocalFileProjectMCPServer:
    def __init__(self, db: Session, project_service: ProjectService, requirement_service: RequirementService) -> None:
        self.db = db
        self.project_service = project_service
        self.requirement_service = requirement_service

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "list_projects", "description": "Возвращает список проектов", "side_effect": False},
            {"name": "get_project_summary", "description": "Возвращает summary проекта", "side_effect": False},
        ]

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "list_projects":
            projects = self.project_service.list_projects()
            return {"projects": [{"id": p.id, "name": p.name, "status": p.status} for p in projects]}
        if tool_name == "get_project_summary":
            return self.project_service.summary(args["project_id"])
        raise ValueError(f"Неизвестный demo MCP tool: {tool_name}")

    def list_resources(self) -> list[dict[str, Any]]:
        return [{"uri": "project://all/summary", "description": "Сводка по всем проектам"}]

    def read_resource(self, resource_uri: str) -> dict[str, Any]:
        if resource_uri == "project://all/summary":
            return {"projects": [self.project_service.summary(project.id) for project in self.project_service.list_projects()]}
        raise ValueError(f"Неизвестный ресурс {resource_uri}")

    def list_prompts(self) -> list[dict[str, Any]]:
        return [{"name": "review_architecture", "description": "Промпт для архитектурного обзора"}]

    def get_prompt(self, prompt_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if prompt_name == "review_architecture":
            return {"prompt": f"Review architecture for project {args.get('project_id', 'unknown')}"}
        raise ValueError(f"Неизвестный prompt {prompt_name}")


class ProjectKnowledgeMCPServer(LocalFileProjectMCPServer):
    def list_tools(self) -> list[dict[str, Any]]:
        return super().list_tools() + [
            {
                "name": "latest_requirement_structure",
                "description": "Возвращает последнюю структуру требований",
                "side_effect": False,
            }
        ]

    def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "latest_requirement_structure":
            structure = self.requirement_service.latest_structure(args["project_id"])
            return {"structure": structure.structured_json if structure else None}
        return super().call_tool(tool_name, args)

