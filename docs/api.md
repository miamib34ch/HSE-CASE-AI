# API

## Основные маршруты
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{id}`
- `POST /api/projects/{id}/requirements/raw`
- `POST /api/projects/{id}/requirements/structure`
- `POST /api/projects/{id}/requirements/confirm`
- `POST /api/projects/{id}/generate/code`
- `POST /api/projects/{id}/generate/tests`
- `POST /api/projects/{id}/deploy`
- `GET /api/projects/{id}/artifacts`
- `GET /api/projects/{id}/runs`
- `GET /api/projects/{id}/summary`
- `GET /api/projects/{id}/generation/logs`
- `GET /api/projects/{id}/test-results`
- `GET /api/projects/{id}/deploy-status`
- `GET /api/providers`
- `POST /api/providers/validate`
- `GET /api/mcp/servers`
- `POST /api/mcp/servers`
- `POST /api/mcp/servers/{id}/validate`
- `GET /api/mcp/servers/{id}/tools`
- `GET /api/mcp/servers/{id}/resources`
- `GET /api/mcp/servers/{id}/prompts`
- `POST /api/mcp/servers/{id}/tools/{tool_name}/call`
- `GET /api/agents`
- `POST /api/agents/execute`
- `GET /api/health`

## MCP server surface
- `GET /mcp/server/tools`
- `GET /mcp/server/resources`
- `GET /mcp/server/prompts`
- `POST /mcp/server/tools/create_project`
- `POST /mcp/server/tools/upload_requirements`
- `POST /mcp/server/tools/structure_requirements`
- `GET /mcp/server/tools/list_projects`

