import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Button, Card, Page, SecondaryButton, TextField } from "../components/ui";
import { endpoints } from "../lib/api";

export function McpPage() {
  const queryClient = useQueryClient();
  const [selectedServerId, setSelectedServerId] = useState<string>("");
  const [serverName, setServerName] = useState("demo-remote-server");
  const serversQuery = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: async () => (await endpoints.mcpServers()).data as Array<Record<string, unknown>>,
  });
  const createServer = useMutation({
    mutationFn: async () =>
      endpoints.createMcpServer({
        name: serverName,
        description: "Remote MCP server, совместимый с /mcp/server",
        transport_type: "streamable_http",
        base_url: "http://localhost:8000/mcp/server",
        command: "",
        args: [],
        env: {},
        auth_type: "none",
        auth_config: {},
        enabled: true,
        trust_level: "remote_verified",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
    },
  });

  const effectiveServerId = selectedServerId || String(serversQuery.data?.[0]?.id || "");
  const toolsQuery = useQuery({
    queryKey: ["mcp-tools", effectiveServerId],
    queryFn: async () => (await endpoints.mcpTools(effectiveServerId)).data as Array<Record<string, unknown>>,
    enabled: Boolean(effectiveServerId),
  });
  const resourcesQuery = useQuery({
    queryKey: ["mcp-resources", effectiveServerId],
    queryFn: async () => (await endpoints.mcpResources(effectiveServerId)).data as Array<Record<string, unknown>>,
    enabled: Boolean(effectiveServerId),
  });
  const promptsQuery = useQuery({
    queryKey: ["mcp-prompts", effectiveServerId],
    queryFn: async () => (await endpoints.mcpPrompts(effectiveServerId)).data as Array<Record<string, unknown>>,
    enabled: Boolean(effectiveServerId),
  });
  const callTool = useMutation({
    mutationFn: async () =>
      endpoints.callMcpTool(effectiveServerId, "list_projects", { args: {}, approved: true }),
  });

  return (
    <Page
      title="MCP Integration Layer"
      subtitle="Управление подключёнными MCP servers, capabilities, вызовами tools и обзор встроенных demo servers."
      actions={<SecondaryButton onClick={() => queryClient.invalidateQueries({ queryKey: ["mcp-servers"] })}>Обновить</SecondaryButton>}
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
        <Card title="MCP servers">
          <div className="mb-4 flex gap-3">
            <TextField value={serverName} onChange={(event) => setServerName(event.target.value)} />
            <Button onClick={() => createServer.mutate()}>Добавить remote</Button>
          </div>
          <div className="space-y-3">
            {serversQuery.data?.map((server) => (
              <button
                key={String(server.id)}
                onClick={() => setSelectedServerId(String(server.id))}
                className={`w-full rounded-2xl border p-4 text-left ${
                  effectiveServerId === String(server.id)
                    ? "border-orange-400 bg-orange-500/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <div className="font-medium">{String(server.name)}</div>
                  <Badge tone={String(server.status) === "healthy" ? "success" : "warn"}>{String(server.status)}</Badge>
                </div>
                <div className="text-sm text-slate-400">{String(server.description || "")}</div>
              </button>
            ))}
          </div>
        </Card>

        <div className="grid gap-6">
          <Card title="Tools">
            <div className="mb-4 flex gap-3">
              <Button onClick={() => callTool.mutate()} disabled={!effectiveServerId}>
                Вызвать list_projects
              </Button>
            </div>
            <pre className="mb-4 whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
              {JSON.stringify(toolsQuery.data ?? [], null, 2)}
            </pre>
            {callTool.data ? (
              <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
                {JSON.stringify(callTool.data.data, null, 2)}
              </pre>
            ) : null}
          </Card>
          <Card title="Resources">
            <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
              {JSON.stringify(resourcesQuery.data ?? [], null, 2)}
            </pre>
          </Card>
          <Card title="Prompts">
            <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
              {JSON.stringify(promptsQuery.data ?? [], null, 2)}
            </pre>
          </Card>
        </div>
      </div>
    </Page>
  );
}
