from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApiMessage(BaseModel):
    message: str


class SummaryResponse(BaseModel):
    project_id: str
    status: str
    counts: dict[str, int]
    last_updated_at: datetime | None = None


class ApprovalRequest(BaseModel):
    approved: bool = Field(default=False)
    notes: str = ""


class JsonPayload(BaseModel):
    payload: dict[str, Any]

