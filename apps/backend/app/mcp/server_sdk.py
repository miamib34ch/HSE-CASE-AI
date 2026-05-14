from __future__ import annotations

from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]


def create_case_mcp_server() -> Any:
    if FastMCP is None:
        return None
    server = FastMCP(name="hse-case-ai")

    @server.tool()
    def create_project(name: str, description: str = "") -> dict[str, str]:
        return {"name": name, "description": description, "status": "accept_request_via_http_bridge"}

    @server.prompt()
    def analyze_requirements() -> str:
        return "Analyze uploaded requirements and produce a normalized structure."

    @server.resource("project://summary")
    def project_summary() -> str:
        return "Use the HTTP API or mounted MCP bridge to resolve project summaries."

    return server
