import axios, { isAxiosError } from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});

export function resolveApiUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${api.defaults.baseURL ?? ""}${path}`;
}

export function describeApiError(error: unknown): string {
  if (isAxiosError(error)) {
    const payload = error.response?.data;
    const detail = payload?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((item) => {
          if (typeof item?.msg === "string" && item.msg) {
            return item.msg;
          }
          if (typeof item === "string" && item) {
            return item;
          }
          return JSON.stringify(item);
        })
        .join(", ");
    }
    const message = payload?.message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    const description = payload?.description;
    if (typeof description === "string" && description.trim()) {
      return description;
    }
    const errorText = payload?.error;
    if (typeof errorText === "string" && errorText.trim()) {
      return errorText;
    }
    if (!error.response) {
      return `Сетевая ошибка при обращении к API (${api.defaults.baseURL ?? "unknown backend"}). Проверьте, что backend запущен и доступен из браузера.`;
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Неизвестная ошибка";
}

export type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type RequirementStructure = {
  id: string;
  project_id: string;
  version: number;
  structured_json: Record<string, unknown>;
  markdown_content: string;
  is_confirmed: boolean;
  created_at: string;
};

export type RequirementDraftResponse = {
  document_id: string;
  content: string;
  structure: RequirementStructure | null;
};

export type ArtifactRead = {
  id: string;
  name: string;
  artifact_type: string;
  path: string;
  version: number;
  size_bytes: number;
  is_text: boolean;
  is_image: boolean;
  download_url: string;
};

export type ArtifactDetail = ArtifactRead & {
  content: string | null;
  encoding: string | null;
};

export type GenerationLog = {
  id: string;
  task_type: string;
  status: string;
  provider: string;
  model: string;
  error_message: string | null;
  output_payload: Record<string, unknown> | null;
};

export type TestResult = {
  id: string;
  status: string;
  passed: number;
  failed: number;
  skipped: number;
  logs: string;
  junit_path: string | null;
  coverage_summary: string | null;
};

export type DeployRun = {
  id: string;
  status: string;
  logs: string;
  dry_run: boolean;
  target_path: string | null;
  preview_url?: string | null;
};

export type DeployResponse = {
  deployment_run_id: string;
  status: string;
  dry_run: boolean;
  logs: string;
  target_path: string | null;
};

export type AssistantChange = {
  path: string;
  reason: string;
  content: string;
};

export type AssistantContextItem = {
  name: string;
  source_type: string;
  included: boolean;
  note: string | null;
};

export type AssistantChatResponse = {
  reply: string;
  used_provider: string;
  used_model: string;
  applied_paths: string[];
  suggested_paths: string[];
  fallback_reason: string | null;
  changes: AssistantChange[];
  context_items: AssistantContextItem[];
};

export type ProviderConfig = {
  provider: string;
  enabled: boolean;
  is_default: boolean;
  config_payload: Record<string, string>;
};

export type ProviderInfo = {
  provider: string;
  enabled: boolean;
  available: boolean;
  default_model: string;
  supports_code: boolean;
  supports_structured: boolean;
  via_gateway: boolean;
  configured: boolean;
  config_fields: Record<string, string>;
};

export type GenerationMode = "auto" | "template" | "llm";

export const endpoints = {
  projects: () => api.get<Project[]>("/api/projects"),
  project: (id: string) => api.get<Project>(`/api/projects/${id}`),
  createProject: (payload: { name: string; description: string }) =>
    api.post<Project>("/api/projects", payload),
  draftRequirements: (
    id: string,
    payload: { description: string; auto_structure: boolean; model?: string; provider?: string; generation_mode?: GenerationMode },
  ) => api.post<RequirementDraftResponse>(`/api/projects/${id}/requirements/draft`, payload),
  uploadRequirements: (id: string, payload: { content: string; source_type: string; filename: string }) =>
    api.post(`/api/projects/${id}/requirements/raw`, payload),
  structureRequirements: (id: string, payload: { provider?: string; model?: string; generation_mode?: GenerationMode }) =>
    api.post<RequirementStructure>(`/api/projects/${id}/requirements/structure`, payload),
  latestStructure: (id: string) =>
    api.get<RequirementStructure | null>(`/api/projects/${id}/requirements/structure/latest`),
  confirmRequirements: (id: string, payload: { approved: boolean; markdown_content?: string; structured_json?: Record<string, unknown> }) =>
    api.post<RequirementStructure>(`/api/projects/${id}/requirements/confirm`, payload),
  generationLogs: (id: string) => api.get<GenerationLog[]>(`/api/projects/${id}/generation/logs`),
  testResults: (id: string) => api.get<TestResult[]>(`/api/projects/${id}/test-results`),
  deployStatus: (id: string) => api.get<DeployRun[]>(`/api/projects/${id}/deploy-status`),
  audit: () => api.get("/api/audit"),
  mcpInvocations: () => api.get("/api/mcp/invocations"),
  generateCode: (id: string, payload: { approved: boolean; provider?: string; model?: string; generation_mode?: GenerationMode }) =>
    api.post(`/api/projects/${id}/generate/code`, payload),
  generateTests: (id: string, payload: { approved: boolean; provider?: string; model?: string; generation_mode?: GenerationMode }) =>
    api.post(`/api/projects/${id}/generate/tests`, payload),
  generateSchemas: (id: string, payload: { approved: boolean; provider?: string; model?: string; generation_mode?: GenerationMode }) =>
    api.post(`/api/projects/${id}/generate/schemas`, payload),
  deploy: (id: string, payload: { approved: boolean; dry_run: boolean }) =>
    api.post<DeployResponse>(`/api/projects/${id}/deploy`, payload),
  assistantChat: (
    id: string,
    payload: { message: string; provider?: string; model?: string; apply_changes: boolean; approved: boolean },
  ) => api.post<AssistantChatResponse>(`/api/projects/${id}/assistant/chat`, payload),
  artifacts: (id: string) => api.get<ArtifactRead[]>(`/api/projects/${id}/artifacts`),
  artifact: (projectId: string, artifactId: string) =>
    api.get<ArtifactDetail>(`/api/projects/${projectId}/artifacts/${artifactId}`),
  uploadArtifact: (projectId: string, formData: FormData) =>
    api.post<ArtifactRead>(`/api/projects/${projectId}/artifacts/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
  updateArtifactText: (projectId: string, artifactId: string, payload: { content: string }) =>
    api.put<ArtifactRead>(`/api/projects/${projectId}/artifacts/${artifactId}/text`, payload),
  deleteArtifact: (projectId: string, artifactId: string) =>
    api.delete(`/api/projects/${projectId}/artifacts/${artifactId}`),
  runs: (id: string) => api.get(`/api/projects/${id}/runs`),
  summary: (id: string) => api.get(`/api/projects/${id}/summary`),
  providers: () => api.get<ProviderInfo[]>("/api/providers"),
  providerModels: (provider: string) => api.get<string[]>(`/api/providers/${provider}/models`),
  providerConfigs: () => api.get<ProviderConfig[]>("/api/providers/configs"),
  saveProviderConfig: (
    provider: string,
    payload: { enabled: boolean; is_default: boolean; config_payload: Record<string, string> },
  ) => api.put<ProviderConfig>(`/api/providers/${provider}/config`, payload),
  validateProvider: (payload: { provider: string; model?: string; payload?: Record<string, unknown> }) =>
    api.post("/api/providers/validate", payload),
  mcpServers: () => api.get("/api/mcp/servers"),
  createMcpServer: (payload: Record<string, unknown>) => api.post("/api/mcp/servers", payload),
  validateMcpServer: (id: string) => api.post(`/api/mcp/servers/${id}/validate`),
  mcpTools: (id: string) => api.get(`/api/mcp/servers/${id}/tools`),
  mcpResources: (id: string) => api.get(`/api/mcp/servers/${id}/resources`),
  mcpPrompts: (id: string) => api.get(`/api/mcp/servers/${id}/prompts`),
  callMcpTool: (id: string, toolName: string, payload: { args: Record<string, unknown>; approved: boolean }) =>
    api.post(`/api/mcp/servers/${id}/tools/${toolName}/call`, payload),
  agents: () => api.get("/api/agents"),
  executeAgent: (payload: Record<string, unknown>) => api.post("/api/agents/execute", payload),
  health: () => api.get("/api/health"),
};
