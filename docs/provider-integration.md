# Интеграция провайдеров

Поддерживаются адаптеры:
- `FakeLLMAdapter`
- `OpenAIAdapter`
- `AnthropicAdapter`
- `GigaChatAdapter`
- `YandexGPTAdapter`
- `OpenRouterAdapter`

## Принцип работы
- Все адаптеры приводят ответы к общему `LLMResult`.
- Реестр `ProviderRegistry` выбирает провайдера по конфигу и при необходимости делает fallback на `fake`.
- Для `OpenRouter` предусмотрен режим gateway/provider.

## Demo mode
Если ключи не заданы, реальные адаптеры не падают, а остаются недоступными для live calls. Платформа автоматически использует `fake`.

