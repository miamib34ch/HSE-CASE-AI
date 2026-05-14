from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.db.models import ProviderConfig
from app.domain.enums.common import TaskType
from app.providers.base import BaseLLMAdapter
from app.providers.fake import FakeLLMAdapter
from app.providers.http_adapters import (
    AnthropicAdapter,
    GigaChatAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
    YandexGPTAdapter,
)


class ProviderRegistry:
    def __init__(
        self,
        settings: Settings,
        provider_configs: dict[str, ProviderConfig] | None = None,
    ) -> None:
        self.settings = settings
        self.provider_configs = provider_configs or {}
        openai_config = self._config_for("openai")
        anthropic_config = self._config_for("anthropic")
        gigachat_config = self._config_for("gigachat")
        yandex_config = self._config_for("yandexgpt")
        openrouter_config = self._config_for("openrouter")
        self._providers: dict[str, BaseLLMAdapter] = {
            "fake": FakeLLMAdapter(),
            "openai": OpenAIAdapter(
                api_key=str(openai_config.get("api_key", settings.openai_api_key)),
                base_url="https://api.openai.com/v1/models",
                model_prefix="gpt",
            ),
            "anthropic": AnthropicAdapter(
                api_key=str(anthropic_config.get("api_key", settings.anthropic_api_key)),
                base_url="https://api.anthropic.com",
                model_prefix="claude",
            ),
            "gigachat": GigaChatAdapter(
                api_key=str(gigachat_config.get("client_secret", settings.gigachat_client_secret)),
                base_url="https://gigachat.devices.sberbank.ru",
                model_prefix="gigachat",
            ),
            "yandexgpt": YandexGPTAdapter(
                api_key=str(yandex_config.get("api_key", settings.yandex_api_key)),
                base_url="https://llm.api.cloud.yandex.net",
                model_prefix="yandexgpt",
                folder_id=str(yandex_config.get("folder_id", settings.yandex_folder_id)),
            ),
            "openrouter": OpenRouterAdapter(
                api_key=str(openrouter_config.get("api_key", settings.openrouter_api_key)),
                base_url="https://openrouter.ai/api/v1/models",
                model_prefix="openrouter",
            ),
        }

    def _config_for(self, provider: str) -> dict[str, Any]:
        config = self.provider_configs.get(provider)
        return dict(config.config_payload) if config is not None else {}

    def list_providers(self) -> list[BaseLLMAdapter]:
        return list(self._providers.values())

    def get(self, provider: str | None = None) -> BaseLLMAdapter:
        selected = provider or self._default_provider_name()
        adapter = self._providers.get(selected)
        if adapter is None:
            return self._providers["fake"]
        if adapter.is_available() or selected == "fake":
            return adapter
        if self.settings.enable_provider_fallback:
            return self._providers["fake"]
        return adapter

    def default_model_for(self, provider: str | None, task_type: str) -> str:
        selected = provider or self._default_provider_name()
        if selected == "fake":
            if task_type == TaskType.CODE_GENERATION.value:
                return "demo-code-v1"
            if task_type == TaskType.TEST_GENERATION.value:
                return "demo-test-v1"
            return "demo-analysis-v1"

        defaults = {
            "openrouter": {
                TaskType.REQUIREMENTS_ANALYSIS.value: "openai/gpt-4o-mini",
                TaskType.CODE_GENERATION.value: "openai/gpt-4o-mini",
                TaskType.TEST_GENERATION.value: "openai/gpt-4o-mini",
                TaskType.SCHEMA_GENERATION.value: "openai/gpt-4o-mini",
            },
            "openai": {
                TaskType.REQUIREMENTS_ANALYSIS.value: "gpt-4o-mini",
                TaskType.CODE_GENERATION.value: "gpt-4o-mini",
                TaskType.TEST_GENERATION.value: "gpt-4o-mini",
                TaskType.SCHEMA_GENERATION.value: "gpt-4o-mini",
            },
            "anthropic": {
                TaskType.REQUIREMENTS_ANALYSIS.value: "claude-3-5-sonnet-latest",
                TaskType.CODE_GENERATION.value: "claude-3-5-sonnet-latest",
                TaskType.TEST_GENERATION.value: "claude-3-5-haiku-latest",
                TaskType.SCHEMA_GENERATION.value: "claude-3-5-haiku-latest",
            },
            "gigachat": {
                TaskType.REQUIREMENTS_ANALYSIS.value: "GigaChat",
                TaskType.CODE_GENERATION.value: "GigaChat",
                TaskType.TEST_GENERATION.value: "GigaChat",
                TaskType.SCHEMA_GENERATION.value: "GigaChat",
            },
            "yandexgpt": {
                TaskType.REQUIREMENTS_ANALYSIS.value: "yandexgpt-lite",
                TaskType.CODE_GENERATION.value: "yandexgpt-lite",
                TaskType.TEST_GENERATION.value: "yandexgpt-lite",
                TaskType.SCHEMA_GENERATION.value: "yandexgpt-lite",
            },
        }
        return defaults.get(selected, {}).get(task_type, self.settings.default_analysis_model)

    def _default_provider_name(self) -> str:
        explicit_default = next(
            (
                config.provider
                for config in self.provider_configs.values()
                if config.is_default and config.enabled
            ),
            None,
        )
        if explicit_default is not None and self._providers.get(explicit_default, self._providers["fake"]).is_available():
            return explicit_default

        first_configured = next(
            (
                name
                for name, config in self.provider_configs.items()
                if config.enabled and name != "fake" and self._providers.get(name, self._providers["fake"]).is_available()
            ),
            None,
        )
        if first_configured is not None:
            return first_configured

        configured_from_env = next(
            (
                name
                for name, adapter in self._providers.items()
                if name != "fake" and adapter.is_available()
            ),
            None,
        )
        if configured_from_env is not None:
            return configured_from_env

        return self.settings.default_llm_provider
