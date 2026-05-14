from typing import cast

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_provider_registry_with_db
from app.db.models import ProviderConfig
from app.domain.enums.common import TaskType
from app.providers.registry import ProviderRegistry
from app.schemas.providers import (
    ProviderConfigRead,
    ProviderConfigUpsert,
    ProviderInfo,
    ProviderValidationRequest,
    ProviderValidationResponse,
)

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderInfo])
def list_providers(
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
) -> list[ProviderInfo]:
    items: list[ProviderInfo] = []
    for provider in registry.list_providers():
        db_config = registry.provider_configs.get(provider.provider_name)
        items.append(
            ProviderInfo(
                provider=provider.provider_name,
                enabled=db_config.enabled if db_config is not None else True,
                available=provider.is_available(),
                default_model=registry.default_model_for(provider.provider_name, TaskType.REQUIREMENTS_ANALYSIS.value),
                supports_code=True,
                supports_structured=True,
                via_gateway=provider.provider_name == "openrouter",
                configured=provider.provider_name == "fake" or provider.is_available(),
                config_fields=mask_config_payload(
                    db_config.config_payload if db_config is not None else {}
                ),
            )
        )
    return items


@router.get("/configs", response_model=list[ProviderConfigRead])
def list_provider_configs(db: Session = Depends(get_db)) -> list[ProviderConfigRead]:
    configs = db.scalars(select(ProviderConfig).order_by(ProviderConfig.provider)).all()
    return [
        ProviderConfigRead(
            provider=item.provider,
            enabled=item.enabled,
            is_default=item.is_default,
            config_payload=mask_config_payload(dict(item.config_payload)),
        )
        for item in configs
    ]


@router.put("/{provider}/config", response_model=ProviderConfigRead)
def upsert_provider_config(
    provider: str,
    payload: ProviderConfigUpsert,
    db: Session = Depends(get_db),
) -> ProviderConfigRead:
    existing = db.scalar(select(ProviderConfig).where(ProviderConfig.provider == provider))
    if payload.is_default:
        db.execute(update(ProviderConfig).values(is_default=False))
    if existing is None:
        existing = ProviderConfig(
            provider=provider,
            enabled=payload.enabled,
            is_default=payload.is_default,
            config_payload=payload.config_payload,
        )
        db.add(existing)
    else:
        existing.enabled = payload.enabled
        existing.is_default = payload.is_default
        existing.config_payload = cast(dict[str, object], payload.config_payload)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return ProviderConfigRead(
        provider=existing.provider,
        enabled=existing.enabled,
        is_default=existing.is_default,
        config_payload=mask_config_payload(dict(existing.config_payload)),
    )


@router.post("/validate", response_model=ProviderValidationResponse)
def validate_provider(
    payload: ProviderValidationRequest,
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
) -> ProviderValidationResponse:
    provider = registry.get(payload.provider)
    health = provider.healthcheck()
    return ProviderValidationResponse(
        provider=payload.provider,
        ok=bool(health.get("ok", False)),
        message=str(health),
        models=provider.list_models(),
    )


@router.get("/{provider}/models", response_model=list[str])
def provider_models(
    provider: str,
    registry: ProviderRegistry = Depends(get_provider_registry_with_db),
) -> list[str]:
    adapter = registry.get(provider)
    return adapter.list_models()


def mask_config_payload(payload: dict[str, object]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in payload.items():
        if not value:
            masked[key] = ""
            continue
        if any(token in key.lower() for token in ["key", "secret", "token"]):
            string_value = str(value)
            masked[key] = f"{string_value[:3]}***{string_value[-2:]}" if len(string_value) > 5 else "***"
        else:
            masked[key] = str(value)
    return masked
