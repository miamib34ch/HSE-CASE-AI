# Безопасность MCP

## Базовые меры
- allowlist для удалённых host через `MCP_ALLOWED_HOSTS`;
- trust levels для каждой связи;
- логирование каждого MCP-вызова;
- подтверждение пользователя для side-effect tools;
- запрет произвольных shell-вызовов внутри MCP layer.

## Ограничения MVP
- Полноценный circuit breaker и OAuth2 abstraction описаны в архитектуре, но реализованы в упрощённом виде.
- Remote MCP transport реализован как безопасный placeholder-слой без полнофункционального streaming proxy.

