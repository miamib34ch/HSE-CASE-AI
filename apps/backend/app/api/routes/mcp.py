from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_correlation_id, get_mcp_service
from app.schemas.mcp import MCPServerCreate, MCPServerRead, MCPToolCallRequest
from app.services.mcp_service import MCPService

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers", response_model=list[MCPServerRead])
def list_servers(service: MCPService = Depends(get_mcp_service)) -> list[MCPServerRead]:
    return [MCPServerRead.model_validate(server, from_attributes=True) for server in service.list_servers()]


@router.post("/servers", response_model=MCPServerRead)
def create_server(
    payload: MCPServerCreate, service: MCPService = Depends(get_mcp_service)
) -> MCPServerRead:
    try:
        server = service.create_server(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MCPServerRead.model_validate(server, from_attributes=True)


@router.post("/servers/{server_id}/validate", response_model=MCPServerRead)
def validate_server(server_id: str, service: MCPService = Depends(get_mcp_service)) -> MCPServerRead:
    try:
        server = service.validate_server(server_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MCPServerRead.model_validate(server, from_attributes=True)


@router.get("/servers/{server_id}/tools")
def list_tools(server_id: str, service: MCPService = Depends(get_mcp_service)) -> list[dict[str, object]]:
    return [
        {
            "id": tool.id,
            "name": tool.name,
            "description": tool.description,
            "side_effect": tool.side_effect,
        }
        for tool in service.list_tools(server_id)
    ]


@router.get("/servers/{server_id}/resources")
def list_resources(server_id: str, service: MCPService = Depends(get_mcp_service)) -> list[dict[str, object]]:
    return [
        {"id": resource.id, "name": resource.name, "uri": resource.uri, "description": resource.description}
        for resource in service.list_resources(server_id)
    ]


@router.get("/servers/{server_id}/prompts")
def list_prompts(server_id: str, service: MCPService = Depends(get_mcp_service)) -> list[dict[str, object]]:
    return [
        {"id": prompt.id, "name": prompt.name, "description": prompt.description}
        for prompt in service.list_prompts(server_id)
    ]


@router.post("/servers/{server_id}/resources/read")
def read_resource(
    server_id: str, payload: dict[str, str], service: MCPService = Depends(get_mcp_service)
) -> dict[str, object]:
    try:
        return service.read_resource(server_id, payload["resource_uri"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/servers/{server_id}/prompts/{prompt_name}")
def get_prompt(
    server_id: str,
    prompt_name: str,
    payload: dict[str, dict[str, object]],
    service: MCPService = Depends(get_mcp_service),
) -> dict[str, object]:
    try:
        return service.get_prompt(server_id, prompt_name, payload.get("args", {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/servers/{server_id}/tools/{tool_name}/call")
def call_tool(
    server_id: str,
    tool_name: str,
    payload: MCPToolCallRequest,
    correlation_id: str = Depends(get_correlation_id),
    service: MCPService = Depends(get_mcp_service),
) -> dict[str, object]:
    try:
        log = service.call_tool(
            server_id=server_id,
            tool_name=tool_name,
            args=payload.args,
            approved=payload.approved,
            correlation_id=correlation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"invocation_id": log.id, "response": log.response_payload, "status": log.status}
