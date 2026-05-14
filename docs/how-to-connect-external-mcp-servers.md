# Подключение внешних MCP servers

1. Откройте экран `MCP`.
2. Добавьте сервер через форму или HTTP API `POST /api/mcp/servers`.
3. Укажите `transport_type`, `base_url`, `auth_type`, `trust_level`.
4. Для удалённого сервера убедитесь, что host присутствует в `MCP_ALLOWED_HOSTS`.
5. Нажмите валидацию или вызовите `POST /api/mcp/servers/{id}/validate`.
6. После синхронизации просмотрите tools/resources/prompts.

