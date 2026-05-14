from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    project_id: str
    agent_name: str = Field(min_length=2)
    task: str
    payload: dict[str, Any] = Field(default_factory=dict)
    approved: bool = False


class AgentExecutionRead(BaseModel):
    id: str
    project_id: str
    task_type: str
    status: str
    logs: str
    created_at: datetime
