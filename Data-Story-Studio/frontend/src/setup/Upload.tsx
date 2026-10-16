import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { fmtDateTime, fmtValue } from "../lib/format";
import type { DatasetListItem } from "../lib/types";
import { IconTrash, IconUpload, Spinner } from "../dashboard/icons";

export function Upload({ onLoaded, onOpen, llm }: { onLoaded: (id: string) => void; onOpen: (id: string) => void; llm: boolean | null }) {
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [recent, setRecent] = useState<DatasetListItem[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.list().then(setRecent).catch(() => {});
  }, []);

  const example = async () => {
    setBusy(true);
    setErr(null);
    try {
      const ds = await api.example();
      onLoaded(ds.id);
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const send = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    setErr(null);
    try {
      const ds = await api.upload(files);
      onLoaded(ds.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-[920px] px-4 sm:px-6 pt-12 sm:pt-20 pb-20">
      <div className="text-[12.5px] font-semibold uppercase tracking-wider text-accent">Data Story Studio</div>
      <h1 className="mt-3 text-[34px] sm:text-[48px] leading-[1.06] font-semibold tracking-tight text-balance">Drop in your data. Get the story behind it.</h1>
      <p className="mt-4 text-[16px] sm:text-[17px] text-ink-2 max-w-[60ch] leading-relaxed">
        Upload one or more CSV or Excel files. We check the data is ready, work out how the files relate, find what matters, then build an animated, explorable dashboard you
        can question, rework and share.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          send([...e.dataTransfer.files]);
        }}
        onClick={() => !busy && input.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        className={`mt-8 card cursor-pointer border-dashed !border-2 p-10 sm:p-14 text-center transition-colors ${drag ? "!border-accent bg-accent-soft" : "!border-line hover:!border-ink-2"}`}
      >
        <input ref={input} type="file" multiple accept=".csv,.tsv,.txt,.xlsx,.xlsm,.xls" className="hidden" onChange={(e) => send([...(e.target.files ?? [])])} />
        {busy ? (
          <div className="flex flex-col items-center gap-3 text-ink-2">
            <Spinner className="w-6 h-6 text-accent" />
            <div className="text-[15px] font-medium text-ink">Reading and profiling your data…</div>
            <div className="text-[13px]">Detecting types, checking quality and looking for links between files</div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-ink text-white grid place-items-center">
              <IconUpload className="w-5 h-5" />
            </div>
            <div className="text-[16px] font-medium">Drop files here, or click to choose</div>
            <div className="text-[13px] text-muted">CSV, TSV or Excel · several files at once is fine · up to 200 MB each</div>
          </div>
        )}
      </div>
      <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-3 rounded-2xl bg-ink text-white p-5">
        <div className="flex-1">
          <div className="text-[15px] font-semibold">New here? Start with the guided example</div>
          <div className="mt-0.5 text-[13px] text-white/70">
            Two years of orders from Brightleaf Coffee Co., a fictional coffee chain: four related files, with step-by-step instructions on each screen.
          </div>
        </div>
        <button onClick={example} disabled={busy} className="shrink-0 px-4 py-2 rounded-xl bg-white text-ink text-[14px] font-medium hover:bg-[#e6f0fc] disabled:opacity-50">
          Try the example
        </button>
      </div>
      {err && <p className="mt-3 text-[13px] text-bad">{err}</p>}
      {llm === false && (
        <p className="mt-3 text-[12.5px] text-muted">
          IBM ICA isn't configured, so dashboards use computed titles and Q&amp;A is off. Add IBM_ICA_ENDPOINT and IBM_ICA_API_KEY to .env to enable the AI narrative.
        </p>
      )}

      <div className="mt-10 grid sm:grid-cols-3 gap-4 text-[13px]">
        {[
          ["1 · Readiness check", "Row counts, missing values, duplicates, date formats and whether multiple files actually connect."],
          ["2 · Story, not charts", "Trends, drivers, anomalies and correlations are ranked by significance. The dashboard leads with the headline."],
          ["3 · Explore & share", "Click to filter, ask questions, redraw any panel, then export an interactive HTML or a PDF report."],
        ].map(([t, d]) => (
          <div key={t}>
            <div className="font-semibold text-ink">{t}</div>
            <div className="mt-1 text-ink-2 leading-relaxed">{d}</div>
          </div>
        ))}
      </div>

      {recent.length > 0 && (
        <div className="mt-14">
          <h2 className="text-[13px] font-semibold text-ink-2 uppercase tracking-wider">Recent</h2>
          <ul className="mt-3 divide-y divide-hair card">
            {recent.slice(0, 8).map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-4 py-3">
                <button className="flex-1 min-w-0 text-left" onClick={() => onLoaded(r.id)}>
                  <div className="text-[14px] font-medium truncate">
                    {r.example && <span className="mr-2 text-[10.5px] font-semibold uppercase tracking-wider text-accent">Example</span>}
                    {r.title ?? r.files.join(", ")}
                  </div>
                  <div className="text-[12px] text-muted truncate">
                    {r.files.join(", ")} · {r.rows !== null ? `${fmtValue(r.rows)} rows · ` : ""}
                    {fmtDateTime(r.created)}
                  </div>
                </button>
                {r.stage === "dashboard" ? (
                  <button onClick={() => onOpen(r.id)} className="px-2.5 py-1.5 rounded-lg bg-ink text-white text-[12.5px] font-medium whitespace-nowrap">
                    View dashboard
                  </button>
                ) : (
                  <span className="text-[11px] text-muted">{r.stage}</span>
                )}
                <button
                  className="p-1.5 rounded-lg text-muted hover:text-bad hover:bg-sunken"
                  aria-label="Delete"
                  onClick={async () => {
                    if (!confirm("Delete this dataset and its dashboards?")) return;
                    await api.remove(r.id);
                    setRecent((x) => x.filter((y) => y.id !== r.id));
                  }}
                >
                  <IconTrash />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
