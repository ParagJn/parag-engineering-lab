import { useEffect, useMemo, useState } from "react";
import OperationCard from "./components/OperationCard";
import OutputPanel from "./components/OutputPanel";
import { fetchOperations, generateContent } from "./api";

const initialForm = {
  niche: "",
  platform: "Instagram",
  audience: "",
  metrics: "",
  extra_context: ""
};

const googleBorderCycle = [
  "border-blue-500 hover:border-blue-600",
  "border-green-500 hover:border-green-600",
  "border-yellow-500 hover:border-yellow-600",
  "border-red-500 hover:border-red-600"
];

export default function App() {
  const [operations, setOperations] = useState([]);
  const [selectedOperation, setSelectedOperation] = useState("");
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [expandedPanel, setExpandedPanel] = useState(null);

  useEffect(() => {
    const loadOperations = async () => {
      try {
        const data = await fetchOperations();
        setOperations(data.operations || []);
        if (data.operations?.length) {
          setSelectedOperation(data.operations[0].id);
        }
      } catch (err) {
        setError(err.message);
      }
    };

    loadOperations();
  }, []);

  const selectedInfo = useMemo(
    () => operations.find((op) => op.id === selectedOperation),
    [operations, selectedOperation]
  );

  const onSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const payload = {
        operation: selectedOperation,
        niche: form.niche,
        platform: form.platform,
        audience: form.audience,
        metrics: form.metrics,
        extra_context: form.extra_context
      };
      const data = await generateContent(payload);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const outputCards = [
    {
      id: "gemini",
      title: "Gemini Agent",
      content: result?.gemini_output,
      accent: "border-blue-500"
    },
    {
      id: "claude",
      title: "Claude Agent",
      content: result?.claude_output,
      accent: "border-green-500"
    },
    {
      id: "synth",
      title: "Synthesized Strategy",
      content: result?.synthesized_output,
      accent: "border-red-500"
    }
  ];

  const expandedCard = outputCards.find((card) => card.id === expandedPanel) || null;

  return (
    <main className="min-h-[100dvh] bg-gradient-to-br from-studio-50 via-slate-100 to-studio-100 px-3 py-4 text-studio-900 sm:px-5 sm:py-6">
      <div className="mx-auto grid w-full max-w-7xl gap-4 lg:grid-cols-[320px_1fr] xl:grid-cols-[360px_1fr]">
        <aside className="rounded-2xl border border-studio-100 bg-white/90 p-4 shadow-panel backdrop-blur sm:p-5 lg:sticky lg:top-6 lg:h-fit">
          <div className="flex items-center gap-3">
            <img src="/app_icon.png" alt="Agentic Social Media Strategist" className="h-10 w-10 sm:h-12 sm:w-12" />
            <h1 className="text-lg font-black tracking-tight text-studio-800 sm:text-xl">Social Media Strategist</h1>
          </div>
          <p className="mt-2 text-xs leading-5 text-studio-600 sm:text-sm sm:leading-6">
            Strategic social media planning powered by Gemini & Claude AI.
          </p>

          <label className="mt-4 block space-y-1 text-sm md:hidden">
            <span className="font-medium text-studio-700">Choose operation</span>
            <select
              className="field"
              value={selectedOperation}
              onChange={(e) => setSelectedOperation(e.target.value)}
            >
              {operations.map((operation) => (
                <option key={operation.id} value={operation.id}>
                  {operation.label}
                </option>
              ))}
            </select>
          </label>

          <div className="mt-4 hidden space-y-3 md:block">
            {operations.map((operation, idx) => (
              <OperationCard
                key={operation.id}
                operation={operation}
                selected={operation.id === selectedOperation}
                onSelect={setSelectedOperation}
                accent={googleBorderCycle[idx % googleBorderCycle.length]}
              />
            ))}
          </div>
        </aside>

        <section className="space-y-4 sm:space-y-5 lg:space-y-6">
          <form onSubmit={onSubmit} className="rounded-2xl border border-studio-100 bg-white p-4 shadow-panel sm:p-5 lg:p-6">
            <h2 className="text-base font-bold text-studio-800 sm:text-lg">Generate Strategy Output</h2>
            <p className="mt-1 text-sm text-studio-600">{selectedInfo?.label || "Select an operation"}</p>

            <div className="mt-4 grid gap-3 sm:mt-5 sm:gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="font-medium text-studio-700">Niche</span>
                <input
                  className="field"
                  placeholder="e.g. Fitness for busy professionals"
                  value={form.niche}
                  onChange={(e) => setForm((prev) => ({ ...prev, niche: e.target.value }))}
                  required
                />
              </label>

              <label className="space-y-1 text-sm">
                <span className="font-medium text-studio-700">Platform</span>
                <input
                  className="field"
                  placeholder="Instagram, LinkedIn, YouTube"
                  value={form.platform}
                  onChange={(e) => setForm((prev) => ({ ...prev, platform: e.target.value }))}
                />
              </label>

              <label className="space-y-1 text-sm md:col-span-2">
                <span className="font-medium text-studio-700">Target Audience</span>
                <textarea
                  className="field min-h-20"
                  placeholder="Describe demographics, behaviors, and goals"
                  value={form.audience}
                  onChange={(e) => setForm((prev) => ({ ...prev, audience: e.target.value }))}
                />
              </label>

              <label className="space-y-1 text-sm md:col-span-2">
                <span className="font-medium text-studio-700">Metrics / Stats</span>
                <textarea
                  className="field min-h-20"
                  placeholder="Paste current reach, engagement, conversion, watch-time stats"
                  value={form.metrics}
                  onChange={(e) => setForm((prev) => ({ ...prev, metrics: e.target.value }))}
                />
              </label>

              <label className="space-y-1 text-sm md:col-span-2">
                <span className="font-medium text-studio-700">Extra Context</span>
                <textarea
                  className="field min-h-24"
                  placeholder="Brand constraints, tone preferences, offer details"
                  value={form.extra_context}
                  onChange={(e) => setForm((prev) => ({ ...prev, extra_context: e.target.value }))}
                />
              </label>
            </div>

            {error ? <p className="mt-4 rounded-lg bg-rose-50 p-2 text-sm text-rose-700">{error}</p> : null}

            <button
              type="submit"
              className="mt-5 w-full rounded-lg bg-studio-700 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-studio-800 disabled:opacity-60 sm:w-auto"
              disabled={loading || !selectedOperation}
            >
              {loading ? "Running agents..." : "Run Multi-Agent Generation"}
            </button>
          </form>

          <div className="grid gap-4 sm:gap-5 lg:grid-cols-2 xl:grid-cols-3">
            {outputCards.map((card) => (
              <OutputPanel
                key={card.id}
                title={card.title}
                content={card.content}
                accent={card.accent}
                compact
                onExpand={() => setExpandedPanel(card.id)}
              />
            ))}
          </div>
        </section>
      </div>

      {expandedCard ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45 p-3 sm:p-6">
          <button
            type="button"
            aria-label="Close expanded card"
            className="absolute inset-0 cursor-default"
            onClick={() => setExpandedPanel(null)}
          />
          <div className="relative z-10 w-full max-w-5xl">
            <div className="mb-3 flex justify-end">
              <button
                type="button"
                onClick={() => setExpandedPanel(null)}
                className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-studio-700 shadow-md"
              >
                Close
              </button>
            </div>
            <OutputPanel
              title={expandedCard.title}
              content={expandedCard.content}
              accent={expandedCard.accent}
            />
          </div>
        </div>
      ) : null}
    </main>
  );
}
