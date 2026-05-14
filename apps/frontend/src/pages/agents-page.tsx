import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Button, Card, Page, TextField } from "../components/ui";
import { endpoints } from "../lib/api";

export function AgentsPage() {
  const [projectId, setProjectId] = useState("");
  const agentsQuery = useQuery({
    queryKey: ["agents"],
    queryFn: async () => (await endpoints.agents()).data as Array<Record<string, unknown>>,
  });
  const executeAgent = useMutation({
    mutationFn: async (agentName: string) =>
      endpoints.executeAgent({
        project_id: projectId,
        agent_name: agentName,
        task: "Проверить текущее состояние CASE pipeline",
        payload: { focus: "demo" },
        approved: true,
      }),
  });

  return (
    <Page
      title="Агентный слой"
      subtitle="Профили агентов, прозрачные handoff и запуск агентных задач поверх LLM adapters и MCP tools."
    >
      <Card title="Запуск агента">
        <div className="mb-5 max-w-xl">
          <label className="mb-2 block text-sm text-slate-300">Project ID</label>
          <TextField value={projectId} onChange={(event) => setProjectId(event.target.value)} placeholder="Укажите project_id для агентного запуска" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agentsQuery.data?.map((agent) => (
            <div key={String(agent.id)} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="font-medium">{String(agent.name)}</div>
                <Badge>{String(agent.approval_mode)}</Badge>
              </div>
              <div className="mb-4 text-sm text-slate-300">{String(agent.role)}</div>
              <Button onClick={() => executeAgent.mutate(String(agent.name))} disabled={!projectId || executeAgent.isPending}>
                Выполнить
              </Button>
            </div>
          ))}
        </div>
        {executeAgent.data ? (
          <pre className="mt-5 whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
            {JSON.stringify(executeAgent.data.data, null, 2)}
          </pre>
        ) : null}
      </Card>
    </Page>
  );
}

