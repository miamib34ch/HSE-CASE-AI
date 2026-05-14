from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class LLMResult:
    provider: str
    model: str
    content: str
    structured_output: dict[str, Any]
    tokens_in: int = 0
    tokens_out: int = 0
    cost_estimate: float = 0.0


class BaseLLMAdapter(Protocol):
    provider_name: str

    def is_available(self) -> bool: ...

    def generate_text(self, *, prompt: str, model: str) -> LLMResult: ...

    def generate_structured(
        self, *, prompt: str, model: str, schema_name: str
    ) -> LLMResult: ...

    def generate_code(self, *, prompt: str, model: str) -> LLMResult: ...

    def generate_tests(self, *, prompt: str, model: str) -> LLMResult: ...

    def healthcheck(self) -> dict[str, Any]: ...

    def list_models(self) -> list[str]: ...

