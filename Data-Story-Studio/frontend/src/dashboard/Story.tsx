import { useMemo, useState } from "react";
import { fmtDateTime, fmtPeriod, fmtValue } from "../lib/format";
import { useMotion, useReveal } from "../lib/motion";
import type { Dashboard, Filter, Insight, Panel } from "../lib/types";
import { KpiCard } from "./Kpi";
import { PanelCard, type PanelActions } from "./PanelCard";
import { IconFilter, IconInfo, IconPause, IconPlay, IconWarn, IconX } from "./icons";

const ROLE_TAG: Record<string, string> = {
  evidence: "The evidence",
  change: "What changed",
  drivers: "The drivers",
  patterns: "Patterns",
  detail: "The detail",
};

/** The whole story view — shared by the live app and the exported HTML viewer. */
export function StoryView({
  dash,
  panels,
  actions,
  filters = [],
  onClearFilter,
  isStatic,
  onInspectKpi,
  toolbar,
}: {
  dash: Dashboard;
  panels: Record<string, Panel>;
  actions: PanelActions;
  filters?: Filter[];
  onClearFilter?: (i: number | "all") => void;
  isStatic?: boolean;
  onInspectKpi?: (p: Panel) => void;
  toolbar?: React.ReactNode;
}) {
  const { story, meta } = dash;
  const kpis = story.kpis.map((k) => panels[k]).filter(Boolean);
  const [inspect, setInspect] = useState<Panel | null>(null);
  const shownIds = useMemo(() => new Set(story.sections.flatMap((s) => s.panels)), [story]);
  const time = meta.time;
  const period = time ? `${fmtPeriod(time.min, "day")} – ${fmtPeriod(time.max, "day")}` : null;

  return (
    <div className="mx-auto max-w-[1240px] px-4 sm:px-6 pb-24">
      <Hero dash={dash} period={period} toolbar={toolbar} />

      {dash.low_confidence && (
        <Banner tone="warn">
          <b>Low-confidence analysis.</b> This dataset has only {fmtValue(meta.rows)} records, below the recommended minimum. Treat trends and differences as
          indicative, not conclusive.
        </Banner>
      )}
      {story.notice && <Banner tone="info">{story.notice}</Banner>}

      {filters.length > 0 && (
        <div className="mt-5 flex flex-wrap items-center gap-2 no-print-hide">
          <span className="inline-flex items-center gap-1 text-[12.5px] text-ink-2">
            <IconFilter className="w-3.5 h-3.5" /> Filtered to
          </span>
          {filters.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 rounded-full bg-accent-soft text-[#184f95] text-[12.5px] pl-2.5 pr-1 py-0.5">
              {f.label ?? `${f.col}: ${f.values.join(", ")}`}
              {onClearFilter && (
                <button className="p-0.5 rounded-full hover:bg-white/60" onClick={() => onClearFilter(i)} aria-label="Remove filter">
                  <IconX className="w-3 h-3" />
                </button>
              )}
            </span>
          ))}
          {onClearFilter && filters.length > 1 && (
            <button className="text-[12px] text-muted hover:text-ink" onClick={() => onClearFilter("all")}>
              Clear all
            </button>
          )}
        </div>
      )}

      {kpis.length > 0 && (
        <section className={`mt-6 grid gap-3 sm:gap-4 ${kpis.length >= 4 ? "grid-cols-2 lg:grid-cols-4" : kpis.length === 3 ? "grid-cols-1 sm:grid-cols-3" : "grid-cols-1 sm:grid-cols-2"}`}>
          {kpis.map((k, i) => (
            <KpiCard key={k.id} panel={k} index={i} onInspect={() => (onInspectKpi ? onInspectKpi(k) : setInspect(k))} />
          ))}
        </section>
      )}

      {story.sections.map((sec, si) => {
        const ps = sec.panels.map((p) => panels[p]).filter(Boolean);
        if (!ps.length) return null;
        return (
          <section key={si} className={`mt-12 ${si > 0 ? "print-break" : ""}`}>
            <SectionHead heading={sec.heading} role={sec.role} note={sec.note} index={si} />
            <div className="mt-5 grid gap-4 grid-cols-1 lg:grid-cols-2">
              {ps.map((p, pi) => {
                const wide = ps.length === 1 || (ps.length % 2 === 1 && pi === 0) || ["table", "small_multiples"].includes(p.chart) || (p.chart === "heatmap" && (p.x_order?.length ?? 0) > 12);
                return (
                  <div key={p.id} className={wide ? "lg:col-span-2" : ""}>
                    <PanelCard panel={p} wide={wide} actions={actions} isStatic={isStatic} tag={p.id === story.headline.panel ? "Headline finding" : undefined} />
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      {(story.insights.length > 0 || (story.next_steps?.length ?? 0) > 0) && <Insights insights={story.insights} next={story.next_steps ?? []} panels={panels} shown={shownIds} />}

      <Provenance dash={dash} />

      {inspect && <KpiInspector panel={inspect} onClose={() => setInspect(null)} />}
    </div>
  );
}

function Hero({ dash, period, toolbar }: { dash: Dashboard; period: string | null; toolbar?: React.ReactNode }) {
  const ref = useReveal<HTMLDivElement>();
  const { story, meta } = dash;
  const { animate, toggle, replay, print } = useMotion();
  return (
    <header ref={ref} className="reveal pt-8 sm:pt-12">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-ink-2">
          <span className="font-medium text-ink">{meta.scope_label}</span>
          <span className="text-line">/</span>
          <span>{fmtValue(meta.rows)} records</span>
          {period && (
            <>
              <span className="text-line">/</span>
              <span>{period}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-1.5 no-print">
          {!print && (
            <>
              <button onClick={replay} className="px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5" title="Replay the animated story">
                <IconPlay className="w-3.5 h-3.5" /> Replay
              </button>
              <button onClick={toggle} className="px-2.5 py-1.5 rounded-lg text-[12.5px] text-ink-2 hover:bg-sunken inline-flex items-center gap-1.5" aria-pressed={!animate} title="Turn motion on or off">
                {animate ? <IconPause className="w-3.5 h-3.5" /> : <IconPlay className="w-3.5 h-3.5" />}
                {animate ? "Motion on" : "Motion off"}
              </button>
            </>
          )}
          {toolbar}
        </div>
      </div>
      <h1 className="mt-5 text-[28px] sm:text-[40px] leading-[1.12] font-semibold tracking-tight text-ink max-w-[22ch] sm:max-w-[26ch] text-balance">{story.headline.title}</h1>
      <div className="mt-4 h-[3px] w-24 rounded-full bg-accent sweep" />
      {story.headline.summary && <p className="mt-4 text-[15.5px] sm:text-[17px] leading-relaxed text-ink-2 max-w-[68ch]">{story.headline.summary}</p>}
      {meta.goal && (
        <p className="mt-3 text-[12.5px] text-muted">
          Built to answer: <span className="text-ink-2">“{meta.goal}”</span>
          {meta.audience ? ` · for ${meta.audience}` : ""}
        </p>
      )}
    </header>
  );
}

function SectionHead({ heading, role, note, index }: { heading: string; role: string; note?: string; index: number }) {
  const ref = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className="reveal">
      <div className="flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-wider text-muted">
        <span className="tabular text-ink">{String(index + 1).padStart(2, "0")}</span>
        <span className="h-px w-6 bg-line" />
        {ROLE_TAG[role] ?? role}
      </div>
      <h2 className="mt-2 text-[21px] sm:text-[24px] font-semibold tracking-tight text-ink text-balance">{heading}</h2>
      {note && <p className="mt-1.5 text-[14px] text-ink-2 max-w-[70ch]">{note}</p>}
    </div>
  );
}

const KIND: Record<Insight["kind"], { label: string; cls: string }> = {
  observation: { label: "Observed", cls: "bg-[#e6f0fc] text-[#184f95]" },
  hypothesis: { label: "Hypothesis", cls: "bg-[#fdf3dc] text-[#7a4f00]" },
  recommendation: { label: "Recommendation", cls: "bg-[#e7f4e7] text-[#006300]" },
};

function Insights({ insights, next, panels }: { insights: Insight[]; next: string[]; panels: Record<string, Panel>; shown: Set<string> }) {
  const ref = useReveal<HTMLDivElement>();
  return (
    <section ref={ref} className="reveal mt-14 print-break">
      <div className="flex items-center gap-2 text-[11.5px] font-semibold uppercase tracking-wider text-muted">
        <span className="h-px w-6 bg-line" />
        What it means
      </div>
      <h2 className="mt-2 text-[21px] sm:text-[24px] font-semibold tracking-tight">Findings and next steps</h2>
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {insights.map((ins, i) => (
          <article key={i} className="card p-5 print-avoid">
            <div className="flex items-center gap-2">
              <span className={`text-[10.5px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${KIND[ins.kind].cls}`}>{KIND[ins.kind].label}</span>
            </div>
            <h3 className="mt-2 text-[15.5px] font-semibold leading-snug">{ins.title}</h3>
            <dl className="mt-3 space-y-2 text-[13px]">
              <Row k="What happened" v={ins.what} />
              <Row k="How significant" v={ins.significance} />
              <Row k="Evidence" v={ins.evidence + (ins.panels.length ? ` (${ins.panels.map((p) => panels[p]?.title).filter(Boolean).slice(0, 1).join("")})` : "")} />
              <Row k="Why it may matter" v={ins.why} />
              <Row k="Next" v={ins.next} />
            </dl>
          </article>
        ))}
      </div>
      {next.length > 0 && (
        <div className="mt-5 card p-5">
          <h3 className="text-[14px] font-semibold">Worth investigating next</h3>
          <ol className="mt-2 space-y-1.5 text-[13.5px] text-ink-2 list-decimal pl-5">
            {next.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  if (!v) return null;
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className="text-ink-2">{v}</dd>
    </div>
  );
}

function Provenance({ dash }: { dash: Dashboard }) {
  const { meta } = dash;
  const [open, setOpen] = useState(false);
  const derived = meta.columns.filter((c) => c.derived);
  return (
    <footer className="mt-14 pt-6 border-t border-hair text-[12.5px] text-ink-2">
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <span>
          <span className="text-muted">Source: </span>
          {meta.files.map((f) => f.name).join(", ")}
        </span>
        {meta.joins.length > 0 && (
          <span>
            <span className="text-muted">Linked on: </span>
            {meta.joins.map((j) => `${j.table} (${j.on})`).join("; ")}
          </span>
        )}
        <span>
          <span className="text-muted">Data loaded: </span>
          {fmtDateTime(Math.max(...meta.files.map((f) => f.uploaded)))}
        </span>
        <span>
          <span className="text-muted">Generated: </span>
          {fmtDateTime(dash.exported ?? dash.generated)}
          {dash.story.source === "ai" ? " · narrative by AI from computed facts" : " · computed narrative"}
        </span>
      </div>
      <button className="mt-3 text-[12px] text-muted hover:text-ink no-print" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Show"} column definitions
      </button>
      {(open || dash.print) && (
        <div className="mt-3 overflow-auto">
          <table className="text-[12px] w-full">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-1 pr-4 font-medium">Column</th>
                <th className="py-1 pr-4 font-medium">Type</th>
                <th className="py-1 pr-4 font-medium">Used as</th>
                <th className="py-1 pr-4 font-medium">Missing</th>
              </tr>
            </thead>
            <tbody>
              {meta.columns.map((c) => (
                <tr key={c.name} className="border-t border-hair">
                  <td className="py-1 pr-4">{c.label}</td>
                  <td className="py-1 pr-4 text-muted">{c.dtype}</td>
                  <td className="py-1 pr-4">
                    {c.role}
                    {c.role === "measure" ? ` (${c.agg === "avg" ? "averaged" : "summed"})` : ""}
                    {c.derived ? ` — derived: ${c.derived}` : ""}
                  </td>
                  <td className="py-1 pr-4 tabular">{(c.missing_pct * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {derived.length > 0 && <p className="mt-2 text-muted">Derived durations exclude rows where the end is before the start.</p>}
        </div>
      )}
      <p className="mt-4 text-[11.5px] text-muted">
        Figures are computed directly from the uploaded data. Missing values are excluded, never treated as zero. Explanations marked “Hypothesis” are possible reasons, not
        established causes.
      </p>
    </footer>
  );
}

export function KpiInspector({ panel, onClose }: { panel: Panel; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/20 flex justify-end no-print" onClick={onClose}>
      <aside className="w-full max-w-[440px] h-full bg-surface shadow-2xl p-6 overflow-auto" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`${panel.measure_label} details`}>
        <div className="flex items-start justify-between">
          <div>
            <div className="text-[12.5px] text-muted">Metric</div>
            <h3 className="text-lg font-semibold">{panel.measure_label}</h3>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-sunken" aria-label="Close">
            <IconX />
          </button>
        </div>
        <div className="mt-4 text-4xl font-semibold tracking-tight">{panel.display}</div>
        <dl className="mt-5 space-y-3 text-[13px]">
          <div>
            <dt className="text-muted">Definition</dt>
            <dd className="text-ink-2">{panel.basis}</dd>
          </div>
          <div>
            <dt className="text-muted">Based on</dt>
            <dd className="text-ink-2">{fmtValue(panel.n)} records{panel.filtered ? " (filtered)" : ""}</dd>
          </div>
          {panel.compare?.display && (
            <div>
              <dt className="text-muted">Latest complete {panel.grain}</dt>
              <dd className="text-ink-2">
                {panel.current_period}: {panel.current_display} ({panel.compare.display} {panel.compare.label})
              </dd>
            </div>
          )}
        </dl>
        {panel.spark && (
          <div className="mt-5">
            <div className="text-[12.5px] text-muted mb-1.5">By {panel.grain}</div>
            <table className="w-full text-[12.5px]">
              <tbody>
                {panel.spark.map(([p, v], i) => (
                  <tr key={i} className="border-t border-hair">
                    <td className="py-1">
                      {fmtPeriod(p, panel.grain)}
                      {panel.spark_partial_last && i === panel.spark!.length - 1 ? " (partial)" : ""}
                    </td>
                    <td className="py-1 text-right tabular">{fmtValue(v, panel.unit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-5">
          <div className="text-[12.5px] text-muted mb-1.5">Query</div>
          <pre className="font-mono text-[11.5px] rounded-lg bg-sunken p-3 overflow-auto prose-sql">{panel.sql}</pre>
        </div>
      </aside>
    </div>
  );
}

export function Banner({ tone, children }: { tone: "warn" | "info" | "bad"; children: React.ReactNode }) {
  const cls = tone === "warn" ? "bg-[#fdf3dc] text-[#5c3d00] border-[#f3dca6]" : tone === "bad" ? "bg-[#fbeaea] text-[#7a1b1b] border-[#f0c9c9]" : "bg-sunken text-ink-2 border-hair";
  const Icon = tone === "info" ? IconInfo : IconWarn;
  return (
    <div className={`mt-5 flex items-start gap-2 rounded-xl border px-4 py-3 text-[13px] ${cls}`}>
      <Icon className="mt-0.5" />
      <div>{children}</div>
    </div>
  );
}
