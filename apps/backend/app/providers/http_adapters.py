from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import LLMResult


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderRequestError(ValueError):
    pass


class HTTPBasedLLMAdapter:
    provider_name = "http"

    def __init__(self, *, api_key: str = "", base_url: str = "", model_prefix: str = "generic") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model_prefix = model_prefix

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError(
                f"Провайдер {self.provider_name} не настроен. Укажите API credentials в .env."
            )

    def _make_result(self, *, model: str, content: str, structured_output: dict[str, Any] | None = None) -> LLMResult:
        return LLMResult(
            provider=self.provider_name,
            model=model,
            content=content,
            structured_output=structured_output or {},
            tokens_in=0,
            tokens_out=max(1, len(content.split())),
        )

    def _headers(self) -> dict[str, str]:
        return {}

    def _request_json(self, *, method: str, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_configured()
        try:
            with httpx.Client(timeout=30.0, headers=self._headers()) as client:
                response = client.request(method=method, url=url, json=payload)
                response.raise_for_status()
                return dict(response.json())
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text.strip()
            if len(response_text) > 300:
                response_text = response_text[:300] + "..."
            raise ProviderRequestError(
                f"Провайдер {self.provider_name} вернул HTTP {exc.response.status_code}: {response_text or exc.response.reason_phrase}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                f"Сетевой сбой при обращении к провайдеру {self.provider_name}: {exc}"
            ) from exc

    def _health(self) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "reason": "API credentials are not configured"}
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(self.base_url)
            return {"ok": response.status_code < 500, "status_code": response.status_code}
        except Exception as exc:  # pragma: no cover
            return {"ok": False, "reason": str(exc)}

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        raise NotImplementedError(f"Provider {self.provider_name} must implement generate_text")

    def generate_structured(
        self, *, prompt: str, model: str, schema_name: str
    ) -> LLMResult:
        content = self.generate_text(prompt=prompt, model=model).content
        return self._make_result(model=model, content=content, structured_output={"schema_name": schema_name, "content": content})

    def generate_code(self, *, prompt: str, model: str) -> LLMResult:
        return self.generate_text(prompt=prompt, model=model)

    def generate_tests(self, *, prompt: str, model: str) -> LLMResult:
        return self.generate_text(prompt=prompt, model=model)

    def healthcheck(self) -> dict[str, Any]:
        return self._health()

    def list_models(self) -> list[str]:
        return [f"{self.model_prefix}-default", f"{self.model_prefix}-latest"]


class OpenAIAdapter(HTTPBasedLLMAdapter):
    provider_name = "openai"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        data = self._request_json(
            method="POST",
            url=self.base_url.replace("/models", "/chat/completions"),
            payload={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
        )
        content = str(data["choices"][0]["message"]["content"])
        return self._make_result(model=model, content=content, structured_output=data)

    def list_models(self) -> list[str]:
        self._ensure_configured()
        with httpx.Client(timeout=15.0, headers=self._headers()) as client:
            response = client.get(self.base_url)
            response.raise_for_status()
            payload = dict(response.json())
        items = payload.get("data", [])
        models = [str(item.get("id", "")) for item in items if isinstance(item, dict) and item.get("id")]
        return models or super().list_models()


class AnthropicAdapter(HTTPBasedLLMAdapter):
    provider_name = "anthropic"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        data = self._request_json(
            method="POST",
            url=self.base_url.rstrip("/") + "/v1/messages",
            payload={"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]},
        )
        parts = data.get("content", [])
        content = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        return self._make_result(model=model, content=content, structured_output=data)

    def list_models(self) -> list[str]:
        self._ensure_configured()
        with httpx.Client(timeout=15.0, headers=self._headers()) as client:
            response = client.get(self.base_url.rstrip("/") + "/v1/models")
            response.raise_for_status()
            payload = dict(response.json())
        items = payload.get("data", [])
        models = [str(item.get("id", "")) for item in items if isinstance(item, dict) and item.get("id")]
        return models or super().list_models()


class GigaChatAdapter(HTTPBasedLLMAdapter):
    provider_name = "gigachat"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        data = self._request_json(
            method="POST",
            url=self.base_url.rstrip("/") + "/api/v1/chat/completions",
            payload={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        content = str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        return self._make_result(model=model, content=content, structured_output=data)


class YandexGPTAdapter(HTTPBasedLLMAdapter):
    provider_name = "yandexgpt"

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "",
        model_prefix: str = "generic",
        folder_id: str = "",
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, model_prefix=model_prefix)
        self.folder_id = folder_id

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Api-Key {self.api_key}", "Content-Type": "application/json"}

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        data = self._request_json(
            method="POST",
            url=self.base_url.rstrip("/") + "/foundationModels/v1/completion",
            payload={
                "modelUri": f"gpt://{self.folder_id}/{model}",
                "completionOptions": {"stream": False, "temperature": 0, "maxTokens": 1024},
                "messages": [{"role": "user", "text": prompt}],
            },
        )
        alternatives = data.get("result", {}).get("alternatives", [])
        content = str(alternatives[0].get("message", {}).get("text", "")) if alternatives else ""
        return self._make_result(model=model, content=content, structured_output=data)


class OpenRouterAdapter(HTTPBasedLLMAdapter):
    provider_name = "openrouter"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def generate_text(self, *, prompt: str, model: str) -> LLMResult:
        data = self._request_json(
            method="POST",
            url=self.base_url.replace("/models", "/chat/completions"),
            payload={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
        )
        content = str(data["choices"][0]["message"]["content"])
        return self._make_result(model=model, content=content, structured_output=data)

    def list_models(self) -> list[str]:
        self._ensure_configured()
        with httpx.Client(timeout=15.0, headers=self._headers()) as client:
            response = client.get(self.base_url)
            response.raise_for_status()
            payload = dict(response.json())
        items = payload.get("data", [])
        models = [str(item.get("id", "")) for item in items if isinstance(item, dict) and item.get("id")]
        return models or super().list_models()
