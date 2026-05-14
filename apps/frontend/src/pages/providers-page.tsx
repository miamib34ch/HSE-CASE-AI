import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Page, SecondaryButton, TextField } from "../components/ui";
import { endpoints, type ProviderConfig } from "../lib/api";

const providerFields: Record<string, Array<{ key: string; label: string; type?: string }>> = {
  openai: [{ key: "api_key", label: "OpenAI API Key", type: "password" }],
  anthropic: [{ key: "api_key", label: "Anthropic API Key", type: "password" }],
  gigachat: [
    { key: "client_id", label: "GigaChat Client ID" },
    { key: "client_secret", label: "GigaChat Client Secret", type: "password" },
  ],
  yandexgpt: [
    { key: "api_key", label: "Yandex API Key", type: "password" },
    { key: "folder_id", label: "Yandex Folder ID" },
  ],
  openrouter: [{ key: "api_key", label: "OpenRouter API Key", type: "password" }],
};

export function ProvidersPage() {
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [enabled, setEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(false);
  const [configPayload, setConfigPayload] = useState<Record<string, string>>({});
  const query = useQuery({
    queryKey: ["providers"],
    queryFn: async () => (await endpoints.providers()).data,
  });
  const modelsQuery = useQuery({
    queryKey: ["provider-models", selectedProvider],
    queryFn: async () => (await endpoints.providerModels(selectedProvider)).data,
    enabled: Boolean(selectedProvider),
  });
  const configsQuery = useQuery({
    queryKey: ["provider-configs"],
    queryFn: async () => (await endpoints.providerConfigs()).data,
  });
  const saveMutation = useMutation({
    mutationFn: async () =>
      endpoints.saveProviderConfig(selectedProvider, {
        enabled,
        is_default: isDefault,
        config_payload: configPayload,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["providers"] });
      await queryClient.invalidateQueries({ queryKey: ["provider-configs"] });
    },
  });
  const validateMutation = useMutation({
    mutationFn: async () => endpoints.validateProvider({ provider: selectedProvider }),
  });

  const selectedConfig = useMemo(() => {
    return configsQuery.data?.find((item: ProviderConfig) => item.provider === selectedProvider) ?? null;
  }, [configsQuery.data, selectedProvider]);

  const fields = providerFields[selectedProvider] ?? [];

  useEffect(() => {
    const nextPayload: Record<string, string> = {};
    for (const field of fields) {
      const value = selectedConfig?.config_payload[field.key] ?? "";
      nextPayload[field.key] = isSecretField(field.key) ? "" : value;
    }
    setEnabled(selectedConfig?.enabled ?? true);
    setIsDefault(selectedConfig?.is_default ?? false);
    setConfigPayload(nextPayload);
  }, [fields, selectedConfig]);

  return (
    <Page
      title="LLM Providers"
      subtitle="Единый реестр провайдеров, demo mode через FakeLLMAdapter и настройка ключей прямо из интерфейса."
    >
      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {query.data?.map((provider) => (
          <Card key={String(provider.provider)}>
            <div className="mb-3 flex items-center justify-between">
              <div className="text-lg font-semibold">{String(provider.provider)}</div>
              <Badge tone={provider.available ? "success" : "warn"}>
                {provider.available ? "available" : "demo/fallback"}
              </Badge>
            </div>
            <div className="space-y-2 text-sm text-slate-300">
              <div>Модель по умолчанию: {String(provider.default_model)}</div>
              <div>Поддержка structured: {String(provider.supports_structured)}</div>
              <div>Поддержка code: {String(provider.supports_code)}</div>
              <div>Сохранённая конфигурация: {provider.configured ? "да" : "нет"}</div>
              <pre className="overflow-auto rounded-2xl border border-white/10 bg-slate-950/60 p-3 text-xs text-slate-400">
                {JSON.stringify(provider.config_fields ?? {}, null, 2)}
              </pre>
            </div>
          </Card>
        ))}
      </div>
      <Card title="Настройка провайдера через UI">
        <div className="grid gap-5 lg:grid-cols-[220px,1fr]">
          <div className="space-y-3">
            {Object.keys(providerFields).map((provider) => (
              <button
                key={provider}
                onClick={() => {
                  setSelectedProvider(provider);
                }}
                className={`w-full rounded-2xl border px-4 py-3 text-left ${
                  selectedProvider === provider
                    ? "border-orange-400 bg-orange-500/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                {provider}
              </button>
            ))}
          </div>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
                Включён
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} />
                По умолчанию
              </label>
            </div>
            {fields.map((field) => (
              <div key={field.key}>
                <label className="mb-2 block text-sm text-slate-300">{field.label}</label>
                <TextField
                  type={field.type ?? "text"}
                  value={configPayload[field.key] ?? ""}
                  onChange={(event) =>
                    setConfigPayload((current) => ({ ...current, [field.key]: event.target.value }))
                  }
                  placeholder={field.label}
                />
              </div>
            ))}
            <div className="flex gap-3">
              <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                Сохранить
              </Button>
              <SecondaryButton onClick={() => validateMutation.mutate()} disabled={validateMutation.isPending}>
                Проверить
              </SecondaryButton>
            </div>
            {selectedConfig ? (
              <pre className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-400">
                {JSON.stringify(selectedConfig, null, 2)}
              </pre>
            ) : null}
            {validateMutation.data ? (
              <pre className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-400">
                {JSON.stringify(validateMutation.data.data, null, 2)}
              </pre>
            ) : null}
            <div>
              <div className="mb-2 text-sm font-medium text-slate-200">Доступные модели</div>
              <pre className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-400">
                {JSON.stringify(modelsQuery.data ?? [], null, 2)}
              </pre>
            </div>
          </div>
        </div>
      </Card>
    </Page>
  );
}

function isSecretField(fieldName: string): boolean {
  return ["key", "secret", "token"].some((token) => fieldName.toLowerCase().includes(token));
}
