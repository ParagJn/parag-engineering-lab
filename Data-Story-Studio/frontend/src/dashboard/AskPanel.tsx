import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { AskResult, Filter, Panel } from "../lib/types";
import { PanelCard } from "./PanelCard";
import { IconChat, IconPin, IconSend, IconX, Spinner } from "./icons";

type Msg = { role: "user" | "assistant"; text: string; result?: AskResult; pinned?: boolean };

const STARTERS = [
  "What changed most in the latest period?",
  "Which segments are performing unusually well or poorly?",
  "Are there any outliers I should look at?",
  "Compare the last two periods and explain the difference",
];

/** Conversational Q&A drawer: every answer comes with the query and the data behind it. */
export function AskPanel({ dsId, scope, filters, open, onClose, onPin, llm }: {
  dsId: string;
  scope: string;
  filters: Filter[];
  open: boolean;
  onClose: () => void;
  onPin: (p: Panel) => Promise<void>;
  llm: boolean | null;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, busy]);
  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 50);
  }, [open]);

  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    const history = msgs.map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const res = await api.ask(dsId, scope, question, history, filters);
      setMsgs((m) => [...m, { role: "assistant", text: res.answer, result: res }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", text: `Something went wrong: ${e.message}`, result: { answer: e.message, kind: "error" } }]);
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <aside className="fixed z-40 inset-y-0 right-0 w-full sm:w-[480px] bg-surface border-l border-hair shadow-2xl flex flex-col no-print" aria-label="Ask about the data">
      <header className="flex items-center justify-between px-5 py-4 border-b border-hair">
        <div className="flex items-center gap-2">
          <IconChat className="text-accent" />
          <h2 className="text-[15px] font-semibold">Ask about this data</h2>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-sunken" aria-label="Close">
          <IconX />
        </button>
      </header>
      <div className="flex-1 overflow-auto px-5 py-4 space-y-4">
        {llm === false && (
          <p className="text-[13px] text-warn bg-[#fdf3dc] rounded-lg px-3 py-2">Questions need IBM ICA. Add IBM_ICA_ENDPOINT and IBM_ICA_API_KEY to .env and restart.</p>
        )}
        {msgs.length === 0 && (
          <div>
            <p className="text-[13.5px] text-ink-2">
              Ask in plain language. Each answer is computed with a query you can inspect, and can be pinned to the dashboard.
              {filters.length > 0 && " Your current filters apply."}
            </p>
            <div className="mt-3 flex flex-col gap-1.5">
              {STARTERS.map((s) => (
                <button key={s} onClick={() => ask(s)} className="text-left px-3 py-2 rounded-lg bg-sunken hover:bg-hair text-[13px] text-ink-2">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-ink text-white px-3.5 py-2 text-[13.5px]">{m.text}</div>
            </div>
          ) : (
            <div key={i}>
              <p className={`text-[13.5px] leading-relaxed ${m.result?.kind === "error" ? "text-bad" : m.result?.kind === "cannot" ? "text-warn" : "text-ink"}`}>{m.text}</p>
              {m.result?.panel && (
                <div className="mt-3">
                  <PanelCard panel={m.result.panel} actions={{ onRunSql: (sql) => api.sql(dsId, scope, sql) }} />
                  <button
                    disabled={m.pinned}
                    onClick={async () => {
                      await onPin(m.result!.panel!);
                      setMsgs((ms) => ms.map((x, k) => (k === i ? { ...x, pinned: true } : x)));
                    }}
                    className="mt-2 inline-flex items-center gap-1.5 text-[12.5px] text-accent hover:underline disabled:text-muted disabled:no-underline"
                  >
                    <IconPin className="w-3.5 h-3.5" />
                    {m.pinned ? "Pinned to dashboard" : "Pin to dashboard"}
                  </button>
                </div>
              )}
              {!!m.result?.follow_ups?.length && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.result.follow_ups.map((f) => (
                    <button key={f} onClick={() => ask(f)} className="px-2.5 py-1 rounded-full text-[12px] bg-sunken hover:bg-hair text-ink-2 text-left">
                      {f}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <Spinner /> <span className="pulse-soft">Working out the query and checking the result…</span>
          </div>
        )}
        <div ref={end} />
      </div>
      <form
        className="p-4 border-t border-hair flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          ask(q);
        }}
      >
        <textarea
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              ask(q);
            }
          }}
          rows={2}
          placeholder="e.g. Which category grew fastest last quarter?"
          className="flex-1 resize-none rounded-xl border border-hair bg-surface px-3 py-2 text-[14px] outline-none focus:border-accent"
        />
        <button disabled={busy || !q.trim()} className="self-end p-2.5 rounded-xl bg-ink text-white disabled:opacity-35" aria-label="Ask">
          <IconSend />
        </button>
      </form>
    </aside>
  );
}
