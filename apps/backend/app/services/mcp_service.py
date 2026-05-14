from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.models import MCPInvocationLog, MCPPrompt, MCPResource, MCPServerConnection, MCPTool
from app.domain.enums.common import RunStatus, TransportType, TrustLevel
from app.mcp.demo_servers import LocalFileProjectMCPServer, ProjectKnowledgeMCPServer
from app.services.projects import ProjectService
from app.services.requirements import RequirementService
from app.utils.dates import utc_now


class MCPService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        project_service: ProjectService,
        requirement_service: RequirementService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.demo_servers = {
            "local-file-project": LocalFileProjectMCPServer(db, project_service, requirement_service),
            "project-knowledge": ProjectKnowledgeMCPServer(db, project_service, requirement_service),
        }
        self._bootstrap_demo_registry()

    def _build_auth_headers(self, server: MCPServerConnection) -> dict[str, str]:
        if server.auth_type == "bearer":
            token = str(server.auth_config.get("token", ""))
            return {"Authorization": f"Bearer {token}"} if token else {}
        if server.auth_type == "api_key":
            header_name = str(server.auth_config.get("header_name", "X-API-Key"))
            value = str(server.auth_config.get("value", ""))
            return {header_name: value} if value else {}
        return {}

    def _remote_request(
        self,
        *,
        server: MCPServerConnection,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
    ) -> Any:
        if not server.base_url:
            raise ValueError("Для remote MCP server не задан base_url")
        url = server.base_url.rstrip("/") + path
        with httpx.Client(timeout=10.0, headers=self._build_auth_headers(server)) as client:
            response = client.request(method=method, url=url, json=json_payload)
            response.raise_for_status()
            return response.json()

    def _bootstrap_demo_registry(self) -> None:
        for name, description in [
            ("local-file-project", "Локальный demo MCP server для проектов"),
            ("project-knowledge", "Локальный demo MCP server для структуры требований"),
        ]:
            existing = self.db.scalar(select(MCPServerConnection).where(MCPServerConnection.name == name))
            if existing:
                continue
            connection = MCPServerConnection(
                name=name,
                description=description,
                transport_type=TransportType.STDIO.value,
                command="builtin",
                enabled=True,
                trust_level=TrustLevel.LOCAL_TRUSTED.value,
                status="healthy",
                capabilities_snapshot={"demo": True},
            )
            self.db.add(connection)
            self.db.commit()
            self.db.refresh(connection)
            self._sync_capabilities(connection.id)

    def _validate_host(self, base_url: str) -> None:
        if not base_url:
            return
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        if host not in self.settings.mcp_allowed_hosts_list:
            raise ValueError("Удалённый MCP host не входит в allowlist")

    def create_server(self, payload: dict[str, Any]) -> MCPServerConnection:
        self._validate_host(str(payload.get("base_url", "")))
        connection = MCPServerConnection(**payload, status="registered", capabilities_snapshot={})
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        self._sync_capabilities(connection.id)
        return connection

    def list_servers(self) -> list[MCPServerConnection]:
        return list(self.db.scalars(select(MCPServerConnection).order_by(MCPServerConnection.created_at.desc())))

    def get_server(self, server_id: str) -> MCPServerConnection:
        server = self.db.get(MCPServerConnection, server_id)
        if server is None:
            raise ValueError("MCP server не найден")
        return server

    def _sync_capabilities(self, server_id: str) -> None:
        server = self.get_server(server_id)
        tools: Sequence[dict[str, Any] | str]
        resources: Sequence[dict[str, Any] | str]
        prompts: Sequence[dict[str, Any] | str]
        self.db.query(MCPTool).filter(MCPTool.server_id == server_id).delete()
        self.db.query(MCPResource).filter(MCPResource.server_id == server_id).delete()
        self.db.query(MCPPrompt).filter(MCPPrompt.server_id == server_id).delete()
        if server.name in self.demo_servers:
            demo = self.demo_servers[server.name]
            tools = demo.list_tools()
            resources = demo.list_resources()
            prompts = demo.list_prompts()
        else:
            try:
                tools_payload = self._remote_request(server=server, method="GET", path="/tools")
                resources_payload = self._remote_request(server=server, method="GET", path="/resources")
                prompts_payload = self._remote_request(server=server, method="GET", path="/prompts")
                tools = list(tools_payload.get("tools", []))
                resources = list(resources_payload.get("resources", []))
                prompts = list(prompts_payload.get("prompts", []))
            except Exception:
                tools = []
                resources = []
                prompts = []
                server.status = "unreachable"
        for tool in tools:
            tool_name = tool["name"] if isinstance(tool, dict) else str(tool)
            self.db.add(
                MCPTool(
                    server_id=server_id,
                    name=tool_name,
                    description=tool.get("description", "") if isinstance(tool, dict) else "",
                    input_schema=tool.get("input_schema", {}) if isinstance(tool, dict) else {},
                    side_effect=tool.get("side_effect", False) if isinstance(tool, dict) else False,
                )
            )
        for resource in resources:
            resource_payload = (
                {"uri": resource, "name": resource, "description": ""}
                if isinstance(resource, str)
                else resource
            )
            self.db.add(
                MCPResource(
                    server_id=server_id,
                    name=resource_payload.get("name", resource_payload["uri"]),
                    uri=resource_payload["uri"],
                    description=resource_payload.get("description", ""),
                )
            )
        for prompt in prompts:
            prompt_payload = (
                {"name": prompt, "description": ""}
                if isinstance(prompt, str)
                else prompt
            )
            self.db.add(
                MCPPrompt(
                    server_id=server_id,
                    name=prompt_payload["name"],
                    description=prompt_payload.get("description", ""),
                    arguments_schema=prompt_payload.get("arguments_schema", {}),
                )
            )
        server.status = "healthy" if server.status != "unreachable" else "unreachable"
        server.last_seen_at = utc_now()
        server.capabilities_snapshot = {"tools": len(tools), "resources": len(resources), "prompts": len(prompts)}
        self.db.add(server)
        self.db.commit()

    def validate_server(self, server_id: str) -> MCPServerConnection:
        self._sync_capabilities(server_id)
        return self.get_server(server_id)

    def list_tools(self, server_id: str) -> list[MCPTool]:
        return list(self.db.scalars(select(MCPTool).where(MCPTool.server_id == server_id)))

    def list_resources(self, server_id: str) -> list[MCPResource]:
        return list(self.db.scalars(select(MCPResource).where(MCPResource.server_id == server_id)))

    def list_prompts(self, server_id: str) -> list[MCPPrompt]:
        return list(self.db.scalars(select(MCPPrompt).where(MCPPrompt.server_id == server_id)))

    def call_tool(
        self, *, server_id: str, tool_name: str, args: dict[str, Any], approved: bool, correlation_id: str
    ) -> MCPInvocationLog:
        server = self.get_server(server_id)
        tool = self.db.scalar(
            select(MCPTool).where(MCPTool.server_id == server_id, MCPTool.name == tool_name)
        )
        if tool is None:
            raise ValueError("MCP tool не найден")
        if tool.side_effect and self.settings.mcp_require_approval_for_side_effect_tools and not approved:
            raise ValueError("Для side-effect MCP tool требуется подтверждение пользователя")
        if server.name in self.demo_servers:
            response_payload = self.demo_servers[server.name].call_tool(tool_name, args)
        else:
            response_payload = self._remote_request(
                server=server,
                method="POST",
                path=f"/tools/{tool_name}/call",
                json_payload={"args": args, "approved": approved},
            )
        log = MCPInvocationLog(
            server_id=server_id,
            tool_name=tool_name,
            request_payload=args,
            response_payload=response_payload,
            status=RunStatus.COMPLETED.value,
            correlation_id=correlation_id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def read_resource(self, server_id: str, resource_uri: str) -> dict[str, Any]:
        server = self.get_server(server_id)
        if server.name in self.demo_servers:
            return self.demo_servers[server.name].read_resource(resource_uri)
        response = self._remote_request(
            server=server,
            method="POST",
            path="/resources/read",
            json_payload={"resource_uri": resource_uri},
        )
        return dict(response)

    def get_prompt(self, server_id: str, prompt_name: str, args: dict[str, Any]) -> dict[str, Any]:
        server = self.get_server(server_id)
        if server.name in self.demo_servers:
            return self.demo_servers[server.name].get_prompt(prompt_name, args)
        response = self._remote_request(
            server=server,
            method="POST",
            path=f"/prompts/{prompt_name}",
            json_payload={"args": args},
        )
        return dict(response)
