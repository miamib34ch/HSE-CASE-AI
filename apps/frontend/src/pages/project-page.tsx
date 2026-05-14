import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  describeApiError,
  endpoints,
  resolveApiUrl,
  type ArtifactRead,
  type AssistantChatResponse,
  type DeployResponse,
  type DeployRun,
  type GenerationMode,
  type GenerationLog,
  type ProviderInfo,
  type TestResult,
} from "../lib/api";
import { MermaidDiagram } from "../components/mermaid-diagram";
import { Badge, Button, Card, Page, SecondaryButton, TextArea } from "../components/ui";

const demoRequirements = `# Система управления задачами

Нужно приложение для команды разработки с проектами, задачами, ролями, комментариями, SLA, уведомлениями и аналитикой.`;
const demoDescription = "Нужен сервис для управления задачами команды разработки: проекты, роли, задачи, комментарии, SLA, уведомления, аналитика и история изменений.";
const generationPreferencesKey = "case_ai_generation_preferences";

type GenerationPreferences = {
  provider: string;
  model: string;
  generationMode: GenerationMode;
};

function loadGenerationPreferences(): GenerationPreferences | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(generationPreferencesKey);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as GenerationPreferences;
  } catch {
    return null;
  }
}

function saveGenerationPreferences(preferences: GenerationPreferences) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(generationPreferencesKey, JSON.stringify(preferences));
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function previewUrl(generation?: GenerationLog, deploy?: DeployRun) {
  const generated = generation?.output_payload?.preview_url;
  if (typeof generated === "string" && generated) {
    return generated;
  }
  if (typeof deploy?.preview_url === "string" && deploy.preview_url) {
    return deploy.preview_url;
  }
  return "";
}

export function ProjectPage() {
  const { projectId = "" } = useParams();
  const queryClient = useQueryClient();
  const cachedPreferences = loadGenerationPreferences();
  const [requirementsText, setRequirementsText] = useState(demoRequirements);
  const [requirementsDescription, setRequirementsDescription] = useState(demoDescription);
  const [selectedProvider, setSelectedProvider] = useState(cachedPreferences?.provider || "fake");
  const [selectedModel, setSelectedModel] = useState(cachedPreferences?.model || "");
  const [generationMode, setGenerationMode] = useState<GenerationMode>(cachedPreferences?.generationMode || "auto");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string>("");
  const [artifactEditor, setArtifactEditor] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [deployFeedback, setDeployFeedback] = useState<DeployResponse | null>(null);
  const [assistantMessage, setAssistantMessage] = useState(
    "Проанализируй последний deploy failure и предложи минимальные правки для generated snapshot.",
  );
  const [assistantApply, setAssistantApply] = useState(false);
  const [assistantResponse, setAssistantResponse] = useState<AssistantChatResponse | null>(null);

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () => (await endpoints.project(projectId)).data,
    enabled: Boolean(projectId),
  });
  const providersQuery = useQuery({
    queryKey: ["providers"],
    queryFn: async () => (await endpoints.providers()).data,
  });
  const modelsQuery = useQuery({
    queryKey: ["provider-models", selectedProvider],
    queryFn: async () => (await endpoints.providerModels(selectedProvider)).data,
    enabled: Boolean(selectedProvider),
  });
  const summaryQuery = useQuery({
    queryKey: ["summary", projectId],
    queryFn: async () => (await endpoints.summary(projectId)).data,
    enabled: Boolean(projectId),
  });
  const artifactsQuery = useQuery({
    queryKey: ["artifacts", projectId],
    queryFn: async () => (await endpoints.artifacts(projectId)).data,
    enabled: Boolean(projectId),
  });
  const runsQuery = useQuery({
    queryKey: ["runs", projectId],
    queryFn: async () => (await endpoints.runs(projectId)).data,
    enabled: Boolean(projectId),
  });
  const latestStructureQuery = useQuery({
    queryKey: ["latestStructure", projectId],
    queryFn: async () => (await endpoints.latestStructure(projectId)).data,
    enabled: Boolean(projectId),
  });
  const generationLogsQuery = useQuery({
    queryKey: ["generationLogs", projectId],
    queryFn: async () => (await endpoints.generationLogs(projectId)).data,
    enabled: Boolean(projectId),
  });
  const testResultsQuery = useQuery({
    queryKey: ["testResults", projectId],
    queryFn: async () => (await endpoints.testResults(projectId)).data,
    enabled: Boolean(projectId),
  });
  const deployStatusQuery = useQuery({
    queryKey: ["deployStatus", projectId],
    queryFn: async () => (await endpoints.deployStatus(projectId)).data,
    enabled: Boolean(projectId),
  });
  const selectedArtifactQuery = useQuery({
    queryKey: ["artifact", projectId, selectedArtifactId],
    queryFn: async () => (await endpoints.artifact(projectId, selectedArtifactId)).data,
    enabled: Boolean(projectId && selectedArtifactId),
  });

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["summary", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["artifacts", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["runs", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["latestStructure", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["generationLogs", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["testResults", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["deployStatus", projectId] }),
    ]);
  };

  useEffect(() => {
    const providers = providersQuery.data ?? [];
    if (!providers.length) {
      return;
    }
    const availableProvider =
      providers.find((provider: ProviderInfo) => provider.available && provider.provider !== "fake") ??
      providers[0];
    if (!selectedProvider) {
      setSelectedProvider(availableProvider.provider);
    }
  }, [providersQuery.data, selectedProvider]);

  useEffect(() => {
    saveGenerationPreferences({
      provider: selectedProvider,
      model: selectedModel,
      generationMode,
    });
  }, [generationMode, selectedModel, selectedProvider]);

  useEffect(() => {
    const models = modelsQuery.data ?? [];
    if (models.length && !models.includes(selectedModel)) {
      setSelectedModel(models[0]);
    }
  }, [modelsQuery.data, selectedModel]);

  useEffect(() => {
    const artifacts = artifactsQuery.data ?? [];
    if (!artifacts.length) {
      setSelectedArtifactId("");
      return;
    }
    const exists = artifacts.some((artifact) => artifact.id === selectedArtifactId);
    if (!selectedArtifactId || !exists) {
      setSelectedArtifactId(artifacts[0].id);
    }
  }, [artifactsQuery.data, selectedArtifactId]);

  useEffect(() => {
    if (selectedArtifactQuery.data?.is_text) {
      setArtifactEditor(selectedArtifactQuery.data.content ?? "");
    }
  }, [selectedArtifactQuery.data]);

  const mutationSuccess = async (text: string) => {
    setFeedback({ kind: "success", text });
    await refreshAll();
  };

  const mutationError = (error: unknown) => {
    setFeedback({ kind: "error", text: describeApiError(error) });
  };

  const uploadRequirements = useMutation({
    mutationFn: async () =>
      (await endpoints.uploadRequirements(projectId, {
        content: requirementsText,
        source_type: "markdown",
        filename: "requirements.md",
      })).data,
    onSuccess: async () => mutationSuccess("Требования загружены."),
    onError: mutationError,
  });
  const draftRequirements = useMutation({
    mutationFn: async () =>
      (
        await endpoints.draftRequirements(projectId, {
          description: requirementsDescription,
          auto_structure: true,
          provider: selectedProvider,
          model: selectedModel || undefined,
          generation_mode: generationMode,
        })
      ).data,
    onSuccess: async (result) => {
      setRequirementsText(result.content);
      await mutationSuccess(
        result.structure
          ? "Черновик требований сгенерирован и сразу структурирован."
          : "Черновик требований сгенерирован.",
      );
    },
    onError: mutationError,
  });
  const structureRequirements = useMutation({
    mutationFn: async () =>
      (
        await endpoints.structureRequirements(projectId, {
          provider: selectedProvider,
          model: selectedModel || undefined,
          generation_mode: generationMode,
        })
      ).data,
    onSuccess: async () => mutationSuccess("Структура требований сгенерирована."),
    onError: mutationError,
  });
  const confirmRequirements = useMutation({
    mutationFn: async () => {
      const structure = latestStructureQuery.data;
      return (
        await endpoints.confirmRequirements(projectId, {
          approved: true,
          markdown_content: structure?.markdown_content,
          structured_json: structure?.structured_json as Record<string, unknown> | undefined,
        })
      ).data;
    },
    onSuccess: async () => mutationSuccess("Структура требований подтверждена."),
    onError: mutationError,
  });
  const generateSchemas = useMutation({
    mutationFn: async () =>
      (
        await endpoints.generateSchemas(projectId, {
          approved: true,
          provider: selectedProvider,
          model: selectedModel || undefined,
          generation_mode: generationMode,
        })
      ).data,
    onSuccess: async (run) => mutationSuccess(`Схемы сгенерированы. Run: ${run.id}`),
    onError: mutationError,
  });
  const generateCode = useMutation({
    mutationFn: async () =>
      (
        await endpoints.generateCode(projectId, {
          approved: true,
          provider: selectedProvider,
          model: selectedModel || undefined,
          generation_mode: generationMode,
        })
      ).data,
    onSuccess: async (run) => mutationSuccess(`Генерация кода завершена. Run: ${run.id}`),
    onError: mutationError,
  });
  const generateTests = useMutation({
    mutationFn: async () =>
      (
        await endpoints.generateTests(projectId, {
          approved: true,
          provider: selectedProvider,
          model: selectedModel || undefined,
          generation_mode: generationMode,
        })
      ).data,
    onSuccess: async (run) => {
      await mutationSuccess(`Генерация тестов завершена. Test run: ${run.test_run_id}. Проверьте блок артефактов: там появились файлы в зоне tests.`);
    },
    onError: mutationError,
  });
  const deploy = useMutation({
    mutationFn: async (dryRun: boolean) =>
      (await endpoints.deploy(projectId, { approved: true, dry_run: dryRun })).data,
    onSuccess: async (result) => {
      setDeployFeedback(result);
      await mutationSuccess(
        `${result.dry_run ? "Dry-run" : "Real deploy"} завершён. Run: ${result.deployment_run_id}, статус: ${result.status}.`,
      );
    },
    onError: mutationError,
  });
  const assistantChat = useMutation({
    mutationFn: async () =>
      (
        await endpoints.assistantChat(projectId, {
          message: assistantMessage,
          provider: selectedProvider,
          model: selectedModel || undefined,
          apply_changes: assistantApply,
          approved: assistantApply,
        })
      ).data,
    onSuccess: async (result) => {
      setAssistantResponse(result);
      await mutationSuccess(
        result.applied_paths.length
          ? `Помощник применил правки: ${result.applied_paths.join(", ")}`
          : "Помощник подготовил анализ и предложения по исправлению.",
      );
    },
    onError: mutationError,
  });
  const uploadArtifact = useMutation({
    mutationFn: async () => {
      if (!uploadFile) {
        throw new Error("Выберите файл для загрузки");
      }
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("artifact_type", "manual_upload");
      return (await endpoints.uploadArtifact(projectId, formData)).data;
    },
    onSuccess: async (artifact) => {
      setUploadFile(null);
      setSelectedArtifactId(artifact.id);
      await mutationSuccess(`Артефакт ${artifact.name} загружен.`);
    },
    onError: mutationError,
  });
  const saveArtifact = useMutation({
    mutationFn: async () => {
      if (!selectedArtifactId) {
        throw new Error("Сначала выберите артефакт");
      }
      return (await endpoints.updateArtifactText(projectId, selectedArtifactId, { content: artifactEditor })).data;
    },
    onSuccess: async (artifact) => {
      setSelectedArtifactId(artifact.id);
      await mutationSuccess(`Текстовый артефакт сохранён как новая версия ${artifact.version}.`);
    },
    onError: mutationError,
  });
  const deleteArtifact = useMutation({
    mutationFn: async (artifactId: string) => {
      if (!artifactId) {
        throw new Error("Сначала выберите артефакт");
      }
      return (await endpoints.deleteArtifact(projectId, artifactId)).data;
    },
    onMutate: async (artifactId: string) => {
      await queryClient.cancelQueries({ queryKey: ["artifact", projectId, artifactId] });
      setSelectedArtifactId("");
    },
    onSuccess: async (result) => {
      setSelectedArtifactId("");
      await mutationSuccess(
        result.status === "already_deleted" ? "Артефакт уже был удалён." : "Артефакт удалён.",
      );
    },
    onError: mutationError,
  });

  const structure = latestStructureQuery.data;
  const artifacts = artifactsQuery.data ?? [];
  const selectedArtifact = selectedArtifactQuery.data;
  const latestGeneration = (generationLogsQuery.data ?? [])[0] as GenerationLog | undefined;
  const latestTests = (testResultsQuery.data ?? [])[0] as TestResult | undefined;
  const latestDeploy = (deployStatusQuery.data ?? [])[0] as DeployRun | undefined;
  const generatedPreviewUrl = previewUrl(latestGeneration, latestDeploy);
  const isMermaidArtifact =
    Boolean(selectedArtifact?.is_text) &&
    (selectedArtifact?.name.endsWith(".mmd") || selectedArtifact?.name.endsWith(".mermaid"));

  return (
    <Page
      title={projectQuery.data?.name ?? "Проект"}
      subtitle="Экран ведения проекта: требования, схемы, артефакты, генерация кода, тесты и локальный деплой."
      actions={<SecondaryButton onClick={() => void refreshAll()}>Обновить данные</SecondaryButton>}
    >
      {feedback ? (
        <div
          className={`mb-6 rounded-2xl border px-4 py-3 text-sm ${
            feedback.kind === "success"
              ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
              : "border-red-400/30 bg-red-500/10 text-red-100"
          }`}
        >
          {feedback.text}
        </div>
      ) : null}

      <div className="mb-6 grid gap-4 lg:grid-cols-4">
        <Card>
          <div className="text-sm text-slate-400">Статус</div>
          <div className="mt-2">
            <Badge tone={projectQuery.data?.status === "deployed" ? "success" : "default"}>
              {projectQuery.data?.status ?? "loading"}
            </Badge>
          </div>
        </Card>
        <Card>
          <div className="text-sm text-slate-400">Артефакты</div>
          <div className="mt-2 text-2xl font-semibold">{summaryQuery.data?.counts?.artifacts ?? 0}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-400">Generation runs</div>
          <div className="mt-2 text-2xl font-semibold">{summaryQuery.data?.counts?.generation_runs ?? 0}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-400">Test runs</div>
          <div className="mt-2 text-2xl font-semibold">{summaryQuery.data?.counts?.test_runs ?? 0}</div>
        </Card>
      </div>

      <Card title="LLM выбор" className="mb-6">
        <div className="grid gap-4 md:grid-cols-3">
          <label className="text-sm text-slate-300">
            <div className="mb-2">Провайдер</div>
            <select
              value={selectedProvider}
              onChange={(event) => {
                setSelectedProvider(event.target.value);
                setSelectedModel("");
              }}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm"
            >
              {(providersQuery.data ?? []).map((provider: ProviderInfo) => (
                <option key={provider.provider} value={provider.provider}>
                  {provider.provider} {provider.available ? "" : "(fallback)"}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-slate-300">
            <div className="mb-2">Режим генерации</div>
            <select
              value={generationMode}
              onChange={(event) => setGenerationMode(event.target.value as GenerationMode)}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm"
            >
              <option value="auto">auto</option>
              <option value="template">template</option>
              <option value="llm">llm</option>
            </select>
          </label>
          <label className="text-sm text-slate-300">
            <div className="mb-2">Модель</div>
            <select
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm"
            >
              {(modelsQuery.data ?? []).map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="mt-3 text-xs text-slate-400">
          `template` использует детерминированные шаблоны. `llm` требует, чтобы модель вернула реальные файлы. `auto` сначала пробует LLM и откатывается на шаблоны при ошибке.
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <Card title="1. Загрузка требований">
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="mb-3 text-sm text-slate-300">
                Можно не писать требования вручную: введите краткое описание системы, и CASE-платформа сгенерирует draft требований и структуру.
              </div>
              <TextArea
                value={requirementsDescription}
                onChange={(event) => setRequirementsDescription(event.target.value)}
                className="min-h-32"
              />
              <div className="mt-3">
                <Button onClick={() => draftRequirements.mutate()} disabled={draftRequirements.isPending}>
                  {draftRequirements.isPending ? "Генерация..." : "Сгенерировать требования по описанию"}
                </Button>
              </div>
            </div>
            <TextArea
              value={requirementsText}
              onChange={(event) => setRequirementsText(event.target.value)}
              className="min-h-64"
            />
            <Button onClick={() => uploadRequirements.mutate()} disabled={uploadRequirements.isPending}>
              {uploadRequirements.isPending ? "Загрузка..." : "Загрузить требования"}
            </Button>
          </div>
        </Card>

        <Card title="2. Структура требований и human-in-the-loop">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => structureRequirements.mutate()} disabled={structureRequirements.isPending}>
                {structureRequirements.isPending ? "Анализ..." : "Структурировать"}
              </Button>
              <SecondaryButton onClick={() => confirmRequirements.mutate()} disabled={!structure}>
                Подтвердить структуру
              </SecondaryButton>
            </div>
            {structure ? (
              <>
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
                  <pre className="whitespace-pre-wrap">{structure.markdown_content}</pre>
                </div>
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
                  <pre className="whitespace-pre-wrap">{formatJson(structure.structured_json)}</pre>
                </div>
              </>
            ) : (
              <div className="text-sm text-slate-400">После запуска анализа здесь появится структура требований.</div>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-4">
        <Card title="3. Генерация схем">
          <div className="space-y-3">
            <div className="text-sm text-slate-300">Создаются Mermaid-артефакты: контекст, ER-схема и модульная карта.</div>
            <Button onClick={() => generateSchemas.mutate()} disabled={generateSchemas.isPending}>
              {generateSchemas.isPending ? "Генерация..." : "Сгенерировать схемы"}
            </Button>
          </div>
        </Card>
        <Card title="4. Генерация кода">
          <div className="space-y-3">
            <div className="text-sm text-slate-300">Будет создан реальный локально разворачиваемый scaffold с Docker Compose и preview URL.</div>
            <Button onClick={() => generateCode.mutate()} disabled={generateCode.isPending}>
              {generateCode.isPending ? "Генерация..." : "Сгенерировать код"}
            </Button>
            {generatedPreviewUrl ? (
              <a
                href={generatedPreviewUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-500/20"
              >
                Preview URL: {generatedPreviewUrl}
              </a>
            ) : null}
          </div>
        </Card>
        <Card title="5. Генерация тестов">
          <div className="space-y-3">
            <div className="text-sm text-slate-300">Тестовые артефакты сохраняются в файловом хранилище и БД.</div>
            <Button onClick={() => generateTests.mutate()} disabled={generateTests.isPending}>
              {generateTests.isPending ? "Генерация..." : "Сгенерировать тесты"}
            </Button>
          </div>
        </Card>
        <Card title="6. Локальный деплой">
          <div className="space-y-3">
            <div className="flex gap-3">
              <Button onClick={() => deploy.mutate(true)} disabled={deploy.isPending}>
                Dry-run
              </Button>
              <SecondaryButton onClick={() => deploy.mutate(false)} disabled={deploy.isPending}>
                Real deploy
              </SecondaryButton>
            </div>
            <div className="text-sm text-slate-400">
              Даже без API-ключей в demo mode должен появиться результат запуска и логи в нижнем блоке.
            </div>
            {deployFeedback ? (
              <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-300">
                <div className="mb-2 font-medium">
                  Последний ответ deploy API: {deployFeedback.dry_run ? "dry-run" : "real deploy"} / {deployFeedback.status}
                </div>
                <pre className="whitespace-pre-wrap">{deployFeedback.logs}</pre>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr,1.1fr]">
        <Card title="Артефакты проекта">
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="mb-3 text-sm text-slate-300">
                Можно загружать свои документы, изображения бизнес-процессов, макеты и другие файлы проекта.
              </div>
              <input
                type="file"
                className="w-full text-sm text-slate-300 file:mr-4 file:rounded-2xl file:border-0 file:bg-orange-500 file:px-4 file:py-2 file:text-white"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
              <div className="mt-3 flex gap-3">
                <Button onClick={() => uploadArtifact.mutate()} disabled={uploadArtifact.isPending || !uploadFile}>
                  {uploadArtifact.isPending ? "Загрузка..." : "Загрузить артефакт"}
                </Button>
                {uploadFile ? <Badge>{uploadFile.name}</Badge> : null}
              </div>
            </div>

            <div className="space-y-3">
              {artifacts.map((artifact: ArtifactRead) => (
                <button
                  key={artifact.id}
                  type="button"
                  onClick={() => setSelectedArtifactId(artifact.id)}
                  className={`w-full rounded-2xl border p-4 text-left transition ${
                    selectedArtifactId === artifact.id
                      ? "border-orange-400/60 bg-orange-500/10"
                      : "border-white/10 bg-white/5 hover:bg-white/10"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{artifact.name}</div>
                    <Badge>{artifact.artifact_type}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">v{artifact.version} · {artifact.size_bytes} bytes</div>
                  <div className="mt-1 break-all text-xs text-slate-500">{artifact.path}</div>
                </button>
              ))}
              {!artifacts.length ? <div className="text-sm text-slate-400">Артефакты ещё не созданы.</div> : null}
            </div>
          </div>
        </Card>

        <Card title="Просмотр и редактирование артефакта">
          {!selectedArtifact ? (
            <div className="text-sm text-slate-400">Выберите артефакт слева, чтобы открыть его.</div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <div className="text-lg font-semibold">{selectedArtifact.name}</div>
                <Badge>{selectedArtifact.artifact_type}</Badge>
                <Badge tone={selectedArtifact.is_text ? "success" : "default"}>v{selectedArtifact.version}</Badge>
              </div>
              <div className="flex flex-wrap gap-3">
                <a
                  href={resolveApiUrl(selectedArtifact.download_url)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-2xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/10"
                >
                  Скачать
                </a>
                {selectedArtifact.is_text ? (
                  <Button onClick={() => saveArtifact.mutate()} disabled={saveArtifact.isPending}>
                    {saveArtifact.isPending ? "Сохранение..." : "Сохранить новую версию"}
                  </Button>
                ) : null}
                <SecondaryButton
                  onClick={() => deleteArtifact.mutate(selectedArtifact.id)}
                  disabled={deleteArtifact.isPending}
                >
                  {deleteArtifact.isPending ? "Удаление..." : "Удалить"}
                </SecondaryButton>
              </div>

              {selectedArtifact.is_text ? (
                <div className="space-y-4">
                  {isMermaidArtifact ? <MermaidDiagram chart={artifactEditor} /> : null}
                  <TextArea
                    value={artifactEditor}
                    onChange={(event) => setArtifactEditor(event.target.value)}
                    className="min-h-96 font-mono text-xs"
                  />
                </div>
              ) : null}

              {selectedArtifact.is_image ? (
                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                  <img
                    src={resolveApiUrl(selectedArtifact.download_url)}
                    alt={selectedArtifact.name}
                    className="max-h-[36rem] w-full rounded-2xl object-contain"
                  />
                </div>
              ) : null}

              {!selectedArtifact.is_text && !selectedArtifact.is_image ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-300">
                  Для этого типа артефакта встроенный редактор не поддерживается. Используйте скачивание.
                </div>
              ) : null}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr,1fr]">
        <Card title="История запусков">
          <div className="space-y-4 text-sm">
            <div>
              <div className="mb-2 font-medium">Generation runs</div>
              <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-300">
                {formatJson(runsQuery.data?.generation_runs ?? [])}
              </pre>
            </div>
            <div>
              <div className="mb-2 font-medium">Test runs</div>
              <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-300">
                {formatJson(runsQuery.data?.test_runs ?? [])}
              </pre>
            </div>
            <div>
              <div className="mb-2 font-medium">Deployment runs</div>
              <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-300">
                {formatJson(runsQuery.data?.deployment_runs ?? [])}
              </pre>
            </div>
          </div>
        </Card>

        <Card title="Последние результаты pipeline">
          <div className="space-y-4 text-sm">
            <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <div className="mb-2 font-medium">Последняя генерация</div>
              <pre className="whitespace-pre-wrap text-xs text-slate-300">{formatJson(latestGeneration ?? {})}</pre>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <div className="mb-2 font-medium">Последний тестовый запуск</div>
              <pre className="whitespace-pre-wrap text-xs text-slate-300">{formatJson(latestTests ?? {})}</pre>
            </div>
            <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
              <div className="mb-2 font-medium">Последний деплой</div>
              <pre className="whitespace-pre-wrap text-xs text-slate-300">{formatJson(latestDeploy ?? {})}</pre>
              {generatedPreviewUrl ? (
                <div className="mt-3">
                  <a
                    href={generatedPreviewUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:bg-emerald-500/20"
                  >
                    Открыть сгенерированный сайт
                  </a>
                </div>
              ) : null}
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Помощник по проекту">
          <div className="space-y-4">
            <div className="text-sm text-slate-300">
              Можно отправить помощнику deploy logs, ошибки сборки или запрос на минимальную правку generated snapshot. Он увидит последний code snapshot и последние deploy logs.
            </div>
            <TextArea
              value={assistantMessage}
              onChange={(event) => setAssistantMessage(event.target.value)}
              className="min-h-36"
            />
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={assistantApply}
                onChange={(event) => setAssistantApply(event.target.checked)}
              />
              Сразу применить минимальные правки в generated snapshot
            </label>
            <div className="flex gap-3">
              <Button onClick={() => assistantChat.mutate()} disabled={assistantChat.isPending}>
                {assistantChat.isPending ? "Анализ..." : "Отправить в помощник"}
              </Button>
            </div>
            {assistantResponse ? (
              <div className="space-y-4">
                <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-200">
                  <div className="mb-2 font-medium">
                    Ответ помощника ({assistantResponse.used_provider} / {assistantResponse.used_model})
                  </div>
                  <pre className="whitespace-pre-wrap text-xs text-slate-300">{assistantResponse.reply}</pre>
                </div>
                {assistantResponse.changes.length ? (
                  <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-200">
                    <div className="mb-2 font-medium">Предлагаемые изменения</div>
                    <pre className="whitespace-pre-wrap text-xs text-slate-300">
                      {formatJson(
                        assistantResponse.changes.map((item) => ({
                          path: item.path,
                          reason: item.reason,
                        })),
                      )}
                    </pre>
                  </div>
                ) : null}
                {assistantResponse.context_items.length ? (
                  <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-200">
                    <div className="mb-2 font-medium">Контекст, который прочитал помощник</div>
                    <pre className="whitespace-pre-wrap text-xs text-slate-300">
                      {formatJson(assistantResponse.context_items)}
                    </pre>
                  </div>
                ) : null}
                {assistantResponse.applied_paths.length ? (
                  <div className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-4 text-sm text-emerald-100">
                    Применены правки: {assistantResponse.applied_paths.join(", ")}
                  </div>
                ) : null}
                {assistantResponse.fallback_reason ? (
                  <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-xs text-amber-100">
                    LLM fallback reason: {assistantResponse.fallback_reason}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </Page>
  );
}
