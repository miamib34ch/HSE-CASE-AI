from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    transport_type: str
    base_url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"
    auth_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    trust_level: str = "local_trusted"


class MCPServerRead(MCPServerCreate):
    id: str
    status: str
    last_seen_at: datetime | None = None
    capabilities_snapshot: dict[str, Any] = Field(default_factory=dict)


class MCPToolCallRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False


class MCPInvocationRead(BaseModel):
    id: str
    server_id: str
    tool_name: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    status: str
    correlation_id: str
