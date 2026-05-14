from typing import Any

from pydantic import BaseModel, Field


class ProviderInfo(BaseModel):
    provider: str
    enabled: bool
    available: bool
    default_model: str
    supports_code: bool
    supports_structured: bool
    via_gateway: bool = False
    configured: bool = False
    config_fields: dict[str, str] = Field(default_factory=dict)


class ProviderConfigRead(BaseModel):
    provider: str
    enabled: bool
    is_default: bool
    config_payload: dict[str, str] = Field(default_factory=dict)


class ProviderConfigUpsert(BaseModel):
    enabled: bool = True
    is_default: bool = False
    config_payload: dict[str, str] = Field(default_factory=dict)


class ProviderValidationRequest(BaseModel):
    provider: str
    model: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ProviderValidationResponse(BaseModel):
    provider: str
    ok: bool
    message: str
    models: list[str]
