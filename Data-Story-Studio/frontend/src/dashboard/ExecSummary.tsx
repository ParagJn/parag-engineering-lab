import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { download, fmtDateTime } from "../lib/format";
import type { ExecSummary } from "../lib/types";
import { IconDownload, IconSpark, IconX, Spinner } from "./icons";

const SECTIONS: [keyof ExecSummary, string][] = [
  ["highlights", "What happened"],
  ["risks", "Risks to watch"],
  ["opportunities", "Opportunities"],
  ["actions", "Recommended actions"],
];

/** Executive commentary drawer: generated once per dashboard, downloadable as Markdown or PDF. */
export function ExecSummaryPanel({ dsId, scope, onClose }: { dsId: string; scope: string; onClose: () => void }) {
  const [s, setS] = useState<ExecSummary | null>(null);
  const [busy, setBusy] = useState<string | null>("load");
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = async (regenerate = false) => {
    setBusy(regenerate ? "regen" : "load");
    setErr(null);
    try {
      setS(await api.summary(dsId, scope, regenerate));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    load();
  }, [dsId, scope]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const get = async (kind: "md" | "pdf") => {
    setBusy(kind);
    setErr(null);
    try {
      const { blob, name } = await api.summaryFile(dsId, scope, kind);
      download(name, blob);
    } catch (e: any) {
      setErr(`Download failed: ${e.message}`);
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    if (!s) return;
    await navigator.clipboard.writeText(s.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const btn = "px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5 disabled:opacity-40";

  return (
    <div className="fixed inset-0 z-50 bg-black/20 flex justify-end no-print" onClick={onClose}>
      <aside className="w-full max-w-[720px] h-full bg-surface shadow-2xl flex flex-col" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Executive summary">
        <div className="flex items-center justify-between gap-3 px-6 py-3 border-b border-hair">
          <div className="text-[12.5px] font-semibold uppercase tracking-wider text-muted">Executive summary</div>
          <div className="flex items-center gap-1">
            <button className={btn} disabled={!s || !!busy} onClick={copy} title="Copy as Markdown, ready to paste into a report">
              {copied ? "Copied" : "Copy"}
            </button>
            <button className={btn} disabled={!s || !!busy} onClick={() => get("md")}>
              {busy === "md" ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />} Markdown
            </button>
            <button className={btn} disabled={!s || !!busy} onClick={() => get("pdf")}>
              {busy === "pdf" ? <Spinner className="w-3.5 h-3.5" /> : <IconDownload className="w-3.5 h-3.5" />} PDF
            </button>
            <button onClick={onClose} className="ml-1 p-1.5 rounded-lg hover:bg-sunken" aria-label="Close">
              <IconX />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto px-6 sm:px-8 py-6">
          {err && <p className="mb-4 text-[13px] text-bad">{err}</p>}
          {busy === "load" && !s && (
            <div className="pt-24 flex flex-col items-center gap-3 text-[13.5px] text-ink-2">
              <Spinner />
              Writing the executive commentary from the dashboard's findings…
            </div>
          )}
          {s && (
            <article className={busy === "regen" ? "opacity-40" : ""}>
              <h2 className="text-[24px] leading-tight font-semibold tracking-tight">{s.title}</h2>
              <p className="mt-1 text-[12.5px] text-muted">
                {s.context} · prepared {fmtDateTime(s.generated)}
              </p>
              {s.notice && <p className="mt-3 rounded-lg bg-[#fdf3dc] px-3 py-2 text-[12.5px] text-warn">{s.notice}</p>}
              {s.bottom_line && (
                <div className="mt-5 rounded-xl bg-sunken border-l-[3px] border-ink px-4 py-3 text-[14.5px] leading-relaxed">
                  <span className="font-semibold">Bottom line. </span>
                  {s.bottom_line}
                </div>
              )}

              {s.metrics.length > 0 && (
                <section className="mt-6">
                  <h3 className="text-[14px] font-semibold border-b border-hair pb-1.5">Key metrics</h3>
                  <table className="mt-1 w-full text-[13px]">
                    <tbody>
                      {s.metrics.map((m) => (
                        <tr key={m.label} className="border-b border-hair">
                          <td className="py-2 pr-3 text-ink-2" title={m.basis}>
                            {m.label}
                          </td>
                          <td className="py-2 pr-3 text-right font-semibold tabular whitespace-nowrap">{m.value}</td>
                          <td className="py-2 text-ink-2">{m.change || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}

              {SECTIONS.map(([key, heading]) => {
                const items = (s[key] as (string | { heading: string; text: string })[]) ?? [];
                if (!items.length) return null;
                const List = key === "actions" ? "ol" : "ul";
                return (
                  <section key={key} className="mt-6">
                    <h3 className="text-[14px] font-semibold border-b border-hair pb-1.5">{heading}</h3>
                    <List className={`mt-2.5 space-y-2 pl-5 text-[14px] leading-relaxed ${key === "actions" ? "list-decimal" : "list-disc"} marker:text-muted`}>
                      {items.map((it, i) =>
                        typeof it === "string" ? (
                          <li key={i}>{it}</li>
                        ) : (
                          <li key={i}>
                            {it.heading && <span className="font-semibold">{it.heading}. </span>}
                            {it.text}
                          </li>
                        ),
                      )}
                    </List>
                  </section>
                );
              })}

              {s.notes.length > 0 && (
                <section className="mt-6">
                  <h3 className="text-[14px] font-semibold border-b border-hair pb-1.5">About the data</h3>
                  <ul className="mt-2.5 space-y-1 pl-5 list-disc text-[12.5px] text-ink-2 marker:text-muted">
                    {s.notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="mt-8 flex items-center justify-between gap-3 border-t border-hair pt-4 text-[12px] text-muted">
                <span>{s.source === "ai" ? "Written by IBM ICA from computed figures; any sentence citing a number not in the data was removed." : "Computed findings (AI commentary off)."}</span>
                <button className={btn} disabled={!!busy} onClick={() => load(true)}>
                  {busy === "regen" ? <Spinner className="w-3.5 h-3.5" /> : <IconSpark className="w-3.5 h-3.5" />} Rewrite
                </button>
              </div>
            </article>
          )}
        </div>
      </aside>
    </div>
  );
}
