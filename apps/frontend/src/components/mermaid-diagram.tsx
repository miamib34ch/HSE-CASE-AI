import { useEffect, useId, useState } from "react";

export function MermaidDiagram({ chart }: { chart: string }) {
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");
  const diagramId = useId().replace(/:/g, "");

  useEffect(() => {
    let active = true;

    async function renderChart() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "dark" });
        const rendered = await mermaid.render(`diagram-${diagramId}`, chart);
        if (!active) {
          return;
        }
        setSvg(rendered.svg);
        setError("");
      } catch (renderError) {
        if (!active) {
          return;
        }
        setError(renderError instanceof Error ? renderError.message : "Не удалось отрисовать Mermaid-схему");
        setSvg("");
      }
    }

    void renderChart();
    return () => {
      active = false;
    };
  }, [chart, diagramId]);

  if (error) {
    return <div className="rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100">{error}</div>;
  }

  return (
    <div
      className="overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/70 p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
