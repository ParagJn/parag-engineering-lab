import { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const prettyJson = (data) => JSON.stringify(data, null, 2);

export default function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [healthStatus, setHealthStatus] = useState("booting"); // "healthy", "down", "booting"

  const stats = useMemo(() => {
    if (!result?.document) return null;
    return [
      { label: "Paragraphs", value: result.document.paragraph_count },
      { label: "Tables", value: result.document.table_count },
      { label: "Images", value: result.document.image_count }
    ];
  }, [result]);

  const healthColor = useMemo(() => {
    switch (healthStatus) {
      case "healthy":
        return "bg-green-500";
      case "down":
        return "bg-red-500";
      case "booting":
        return "bg-yellow-500";
      default:
        return "bg-gray-400";
    }
  }, [healthStatus]);

  const healthLabel = useMemo(() => {
    switch (healthStatus) {
      case "healthy":
        return "Server online";
      case "down":
        return "Server offline";
      case "booting":
        return "Connecting...";
      default:
        return "Unknown";
    }
  }, [healthStatus]);

  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_URL}/health`, {
        method: "GET",
        signal: AbortSignal.timeout(5000), // 5 second timeout
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.status === "ok") {
          setHealthStatus("healthy");
        } else {
          setHealthStatus("down");
        }
      } else {
        setHealthStatus("down");
      }
    } catch (err) {
      setHealthStatus("down");
    }
  };

  useEffect(() => {
    // Check health immediately on mount
    checkHealth();

    // Poll health every 10 seconds
    const interval = setInterval(checkHealth, 10000);

    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError("Please select a .docx file.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);

      const response = await fetch(`${API_URL}/process`, {
        method: "POST",
        body: form
      });

      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.detail || "Processing failed.");
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Unexpected error.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen app-shell overflow-x-hidden">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <header className="flex flex-col gap-4 sm:gap-6">
          <div className="inline-flex items-center gap-3 text-sm font-medium text-ocean bg-white/70 px-4 py-2 rounded-full shadow-soft w-fit">
            <span className={`w-2 h-2 rounded-full ${healthColor}`} title={healthLabel}></span>
            {healthStatus === "down" ? "API Server Down" : "API Server Running"}
          </div>
          <div className="flex flex-col gap-3">
            <h1 className="text-3xl sm:text-4xl md:text-5xl font-display text-ink break-words">
              Docx context builder for Milvus-ready ingestion
            </h1>
            <p className="text-base sm:text-lg text-ink/70 max-w-2xl">
              Upload a Word document, extract text, tables, and images, and receive
              a structured JSON payload tailored for semantic search workflows.
            </p>
          </div>
        </header>

        <main className="mt-6 sm:mt-10 grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-6 sm:gap-8">
          <section className="bg-white/80 backdrop-blur rounded-3xl p-4 sm:p-6 shadow-soft border border-white">
            <h2 className="text-lg sm:text-xl font-display mb-4">Upload a document</h2>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <label className="border-2 border-dashed border-slate rounded-2xl p-4 sm:p-6 flex flex-col gap-3 cursor-pointer hover:border-gold transition">
                <span className="text-sm uppercase tracking-wide text-ink/50">Docx file</span>
                <span className="text-base sm:text-lg font-medium text-ink break-all">
                  {file ? file.name : "Drop your .docx here or click to browse"}
                </span>
                <input
                  type="file"
                  accept=".docx"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
              <button
                type="submit"
                disabled={loading}
                className="bg-ink text-white py-3 rounded-2xl font-medium hover:bg-ocean transition disabled:opacity-60"
              >
                {loading ? "Processing..." : "Generate context JSON"}
              </button>
              {error && (
                <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
                  {error}
                </div>
              )}
            </form>

            {result && (
              <div className="mt-6 bg-slate/50 rounded-2xl p-4 text-sm text-ink/70 break-words">
                <div className="font-medium text-ink">Document summary</div>
                <div className="mt-2 break-all">{result.document.filename}</div>
                <div className="break-words">{result.document.processed_at}</div>
              </div>
            )}
          </section>

          <section className="flex flex-col gap-4 sm:gap-6">
            <div className="bg-white/80 backdrop-blur rounded-3xl p-4 sm:p-6 shadow-soft border border-white">
              <h2 className="text-lg sm:text-xl font-display mb-4">Extraction highlights</h2>
              {stats ? (
                <div className="grid grid-cols-3 gap-2 sm:gap-4">
                  {stats.map((stat) => (
                    <div
                      key={stat.label}
                      className="bg-sky/70 rounded-2xl p-3 sm:p-4 text-center"
                    >
                      <div className="text-xl sm:text-2xl font-display text-ink">
                        {stat.value}
                      </div>
                      <div className="text-xs uppercase tracking-wide text-ink/60">
                        {stat.label}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-ink/60">
                  Upload a document to see the extracted content breakdown.
                </p>
              )}
            </div>

            <div className="bg-white/90 backdrop-blur rounded-3xl p-4 sm:p-6 shadow-soft border border-white">
              <h2 className="text-lg sm:text-xl font-display mb-4">Vector payload</h2>
              <p className="text-sm text-ink/60 mb-3">
                Copy the JSON below into your ingestion pipeline. The
                <span className="font-medium text-ink"> vector_records </span>
                array is optimized for semantic search indexing.
              </p>
              <pre className="bg-ink text-white text-xs rounded-2xl p-3 sm:p-4 max-h-[360px] overflow-auto break-all whitespace-pre-wrap">
                {result ? prettyJson(result) : "Waiting for a document..."}
              </pre>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
