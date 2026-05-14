# Агенты и MCP

В MVP определены профили:
- RequirementsAnalystAgent
- SoftwareArchitectAgent
- CodeGeneratorAgent
- TestEngineerAgent
- DeploymentAgent
- ReviewerAgent

Каждый профиль хранит:
- системный промпт;
- разрешённые LLM providers;
- разрешённые MCP servers;
- разрешённые tools;
- approval mode;
- retry policy;
- timeout.

При выполнении агентной задачи сохраняются:
- `AgentExecution`;
- `AgentMemorySnapshot`;
- `AgentHandoff`.

