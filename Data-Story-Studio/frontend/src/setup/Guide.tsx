import { useState } from "react";
import { IconCheck, IconX } from "../dashboard/icons";

type Step = { title: string; body: string };

const STEPS: Record<"readiness" | "dashboard", { heading: string; steps: Step[] }> = {
  readiness: {
    heading: "Guided example · step 1 of 2: check the data",
    steps: [
      {
        title: "Four related files were uploaded",
        body: "Orders (CSV) is the main table. Products and Stores (an Excel file) describe it, and Feedback holds survey answers. The coloured chips under each file show how every column will be used: measure, category, date or identifier. Hover a chip for its details.",
      },
      {
        title: "The links were found automatically",
        body: "Under “How the files fit together”, each link shows its match rate. Feedback only covers about 30% of orders, so you'll see a warning. That's expected: not every customer fills in the survey.",
      },
      {
        title: "Fix a quality issue",
        body: "The orders export has a few exact duplicate rows. Under Quality checks, click “Remove duplicates” and watch the counts update.",
      },
      {
        title: "Tell it what you care about",
        body: "Pick one of the suggested goals, or type your own. Goals steer which story leads, but every figure still comes from the data.",
      },
      {
        title: "Build the dashboard",
        body: "Click “Build the dashboard”. With fewer than 1,000 records (try the small file in samples/) you'd be asked for more data first.",
      },
    ],
  },
  dashboard: {
    heading: "Guided example · step 2 of 2: explore the story",
    steps: [
      { title: "Read the headline", body: "The top line is the most significant finding. KPI cards show the latest complete period compared with the one before. Click a KPI to see its definition, monthly values and query." },
      { title: "Click to filter", body: "Click a bar (a channel or store) or a heatmap cell and every panel recomputes for that slice, titles included. Remove the filter with the chip at the top." },
      { title: "Check the evidence", body: "Each panel has a table icon (the data behind it, downloadable as CSV) and a code icon (the exact SQL, which you can edit and run)." },
      { title: "Redraw a panel", body: "Click the wand on any panel. Switch the chart type, change the time grain, or type a change such as “split by channel” or “only the top 3”. Undo is there if you don't like it." },
      { title: "Ask a question", body: "Click Ask and try “Which store has the longest waits?” or “How did revenue change after January 2026?”. Pin a good answer to the dashboard." },
      { title: "Find more", body: "Below the dashboard, “Show more findings” lists the other views the analysis considered. Add any of them back." },
      { title: "Share it", body: "Download an HTML report (interactive, works offline) or a PDF. Use Replay to watch the animated story again, or turn motion off." },
    ],
  },
};

/** Coach card shown when the built-in example is loaded; tick steps off as you go. */
export function Guide({ stage }: { stage: "readiness" | "dashboard" }) {
  const key = `dv-guide-${stage}`;
  const [done, setDone] = useState<number[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? "[]");
    } catch {
      return [];
    }
  });
  const [hidden, setHidden] = useState(false);
  const { heading, steps } = STEPS[stage];
  const toggle = (i: number) => {
    const next = done.includes(i) ? done.filter((x) => x !== i) : [...done, i];
    setDone(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  };
  if (hidden)
    return (
      <button onClick={() => setHidden(false)} className="mt-5 text-[12.5px] text-accent hover:underline no-print">
        Show the guide
      </button>
    );
  return (
    <section className="mt-5 rounded-2xl border border-[#cde2fb] bg-[#f3f8fe] p-5 no-print" aria-label="How to use this tool">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11.5px] font-semibold uppercase tracking-wider text-accent">How to use this tool</div>
          <h2 className="mt-1 text-[16px] font-semibold text-ink">{heading}</h2>
        </div>
        <button onClick={() => setHidden(true)} className="p-1.5 rounded-lg text-muted hover:text-ink hover:bg-white/70" aria-label="Hide guide">
          <IconX />
        </button>
      </div>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {steps.map((s, i) => {
          const isDone = done.includes(i);
          return (
            <li key={i} className={`rounded-xl bg-surface border border-[#e1ecfa] p-3.5 transition-opacity ${isDone ? "opacity-60" : ""}`}>
              <div className="flex items-start gap-2.5">
                <button
                  onClick={() => toggle(i)}
                  aria-pressed={isDone}
                  aria-label={isDone ? "Mark as not done" : "Mark as done"}
                  className={`mt-0.5 w-5 h-5 shrink-0 rounded-full grid place-items-center text-[11px] font-semibold ${isDone ? "bg-ink text-white" : "border border-line text-ink-2 hover:border-ink"}`}
                >
                  {isDone ? <IconCheck className="w-3 h-3" /> : i + 1}
                </button>
                <div>
                  <div className="text-[13.5px] font-semibold text-ink">{s.title}</div>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-ink-2">{s.body}</p>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-[11.5px] text-muted">Brightleaf Coffee Co. is fictional; the data is generated by scripts/make_example.py.</p>
    </section>
  );
}
