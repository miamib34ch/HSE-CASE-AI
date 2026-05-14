# MCP-архитектура

## Зачем системе MCP
MCP нужен для подключения внешних инструментов, ресурсов знаний и prompt servers, а также для публикации самой CASE-платформы как инструмента для других AI-clients и IDE agents.

## CASE-платформа как MCP client
- В БД хранится registry подключений `MCPServerConnection`.
- Для каждого сервера сохраняются tools/resources/prompts и invocation logs.
- Поддерживаются встроенные demo servers и remote placeholder servers.

## CASE-платформа как MCP server
- Публикуется HTTP surface `/mcp/server/...` для demo-вызовов.
- При наличии официального Python MCP SDK может быть создан объект `FastMCP` через `app/mcp/server_sdk.py`.
- Отсутствие SDK не ломает систему: для demo и локальной интеграции используется HTTP bridge.

## Tools / Resources / Prompts
- Tools: операции управления проектом и pipeline.
- Resources: состояния проекта, требования, артефакты, summary.
- Prompts: анализ требований, генерация backend/frontend, тестов и архитектурный review.

## Агентный слой и MCP
Агенты вызывают MCP tools в рамках разрешённых политик. При side-effect операциях действует approval flow.

## Approval flow и trust model
- `local_trusted`: встроенные и локальные доверенные серверы.
- `remote_verified`: удалённые серверы из allowlist.
- `remote_untrusted`: недоверенные серверы, для которых должны действовать ограничения.
