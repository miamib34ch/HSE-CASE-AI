import { useQuery } from "@tanstack/react-query";
import { Card, Page } from "../components/ui";
import { endpoints } from "../lib/api";

export function LogsPage() {
  const auditQuery = useQuery({
    queryKey: ["audit"],
    queryFn: async () => (await endpoints.audit()).data,
  });
  const mcpQuery = useQuery({
    queryKey: ["mcp-invocations"],
    queryFn: async () => (await endpoints.mcpInvocations()).data,
  });

  return (
    <Page
      title="Логи и audit trail"
      subtitle="Сводный экран по audit events и журналу MCP-вызовов для демонстрации прозрачности и human-in-the-loop."
    >
      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Audit events">
          <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
            {JSON.stringify(auditQuery.data ?? [], null, 2)}
          </pre>
        </Card>
        <Card title="MCP invocation logs">
          <pre className="whitespace-pre-wrap rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-xs text-slate-300">
            {JSON.stringify(mcpQuery.data ?? [], null, 2)}
          </pre>
        </Card>
      </div>
    </Page>
  );
}

